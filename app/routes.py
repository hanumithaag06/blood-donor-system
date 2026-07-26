"""
API Layer — all REST endpoints, grouped by resource.
Routes stay thin: parse request -> call service -> return response.
No business logic lives here; that's all in app/services/.
"""
from datetime import date
from flask import Blueprint, request, jsonify
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError

from app.db import get_session
from app.services.donor_service import DonorService
from app.services.eligibility_service import EligibilityService
from app.services.search_service import SearchService
from app.services.prediction_service import PredictionService
from app.assistant import Assistant
from app.repository import DonationRepository
from app.schemas import (
    DonorCreateSchema, DonorUpdateSchema, DonorResponseSchema,
    DonationCreateSchema, DonationResponseSchema, DonationCompleteSchema,
    DonorLookupSchema, SearchQuerySchema, AssistantQuerySchema,
    DashboardStatsSchema, DonorDetailsResponseSchema,
)
from app.utils import get_logger, AppError
from app.settings import settings

logger = get_logger(__name__)
api = Blueprint("api", __name__)


@api.errorhandler(AppError)
def handle_app_error(error: AppError):
    return jsonify({"error": error.message}), error.status_code


@api.errorhandler(IntegrityError)
def handle_integrity_error(error: IntegrityError):
    return jsonify({"error": "Database constraint violated", "details": str(error.orig)}), 400


@api.errorhandler(PydanticValidationError)
def handle_validation_error(error: PydanticValidationError):
    return jsonify({"error": "Validation failed", "details": error.errors()}), 400


@api.route("/areas", methods=["GET"])
def list_areas():
    return jsonify(list(settings.CHENNAI_AREAS)), 200


# ---------- Donor Routes ----------

@api.route("/donors", methods=["GET"])
def list_donors():
    with get_session() as session:
        service = DonorService(session)
        donors = service.list_donors()
        result = [DonorResponseSchema.model_validate(d).model_dump(mode="json") for d in donors]
        return jsonify(result), 200


@api.route("/donors", methods=["POST"])
def create_donor():
    with get_session() as session:
        payload = DonorCreateSchema(**request.get_json())
        service = DonorService(session)
        donor = service.create_donor(payload)
        return jsonify(DonorResponseSchema.model_validate(donor).model_dump(mode="json")), 201


@api.route("/donors/<int:donor_id>", methods=["GET"])
def get_donor(donor_id: int):
    with get_session() as session:
        service = DonorService(session)
        donor = service.get_donor(donor_id)
        return jsonify(DonorResponseSchema.model_validate(donor).model_dump(mode="json")), 200


@api.route("/donors/<int:donor_id>", methods=["PUT"])
def update_donor(donor_id: int):
    with get_session() as session:
        payload = DonorUpdateSchema(**request.get_json())
        service = DonorService(session)
        donor = service.update_donor(donor_id, payload)
        return jsonify(DonorResponseSchema.model_validate(donor).model_dump(mode="json")), 200


@api.route("/donors/<int:donor_id>/donations", methods=["GET"])
def get_donation_history(donor_id: int):
    with get_session() as session:
        service = DonorService(session)
        donations = service.get_donation_history(donor_id)
        result = [DonationResponseSchema.model_validate(d).model_dump(mode="json") for d in donations]
        return jsonify(result), 200


@api.route("/donations", methods=["POST"])
def add_donation():
    with get_session() as session:
        payload = DonationCreateSchema(**request.get_json())
        service = DonorService(session)
        donation = service.add_donation(payload)
        return jsonify(DonationResponseSchema.model_validate(donation).model_dump(mode="json")), 201


# ---------- Mode 2: Donor Lookup ----------

@api.route("/donors/lookup", methods=["GET"])
def lookup_donor():
    phone_number = request.args.get("phone_number")
    donor_id = request.args.get("donor_id", type=int)
    with get_session() as session:
        service = DonorService(session)
        donor = service.find_donor_for_update(phone_number=phone_number, donor_id=donor_id)
        return jsonify(DonorResponseSchema.model_validate(donor).model_dump(mode="json")), 200


# ---------- Donation Completion Workflow ----------

@api.route("/donors/<int:donor_id>/complete-donation", methods=["POST"])
def complete_donation(donor_id: int):
    with get_session() as session:
        payload = DonationCompleteSchema(**request.get_json())
        service = DonorService(session)
        result = service.complete_donation(donor_id, payload)
        return jsonify({
            "donor_id": result["donor_id"],
            "is_available": result["is_available"],
            "total_donations": result["total_donations"],
            "eligibility": result["eligibility"].model_dump(mode="json"),
        }), 200


# ---------- Availability Toggle (admin) ----------

@api.route("/donors/<int:donor_id>/availability", methods=["PATCH"])
def set_availability(donor_id: int):
    body = request.get_json()
    if "is_available" not in body:
        return jsonify({"error": "is_available field is required"}), 400
    with get_session() as session:
        service = DonorService(session)
        donor = service.set_availability(donor_id, bool(body["is_available"]))
        return jsonify(DonorResponseSchema.model_validate(donor).model_dump(mode="json")), 200


# ---------- Eligibility Route ----------

@api.route("/eligibility/<int:donor_id>", methods=["GET"])
def check_eligibility(donor_id: int):
    with get_session() as session:
        donor_service = DonorService(session)
        donor = donor_service.get_donor(donor_id)
        last_donation = donor_service.get_last_donation_date(donor_id)

        eligibility_service = EligibilityService()
        result = eligibility_service.check_eligibility(
            donor_id=donor_id,
            date_of_birth=donor.date_of_birth,
            last_donation_date=last_donation,
        )
        # NEW: computed here, no service logic duplicated
        if result.next_eligible_date and not result.is_eligible:
            result.days_remaining = (result.next_eligible_date - date.today()).days

        return jsonify(result.model_dump(mode="json")), 200


# ---------- Search Route ----------

@api.route("/search", methods=["GET"])
def search_donors():
    show_all = request.args.get("all", "").lower() == "true"
    query = SearchQuerySchema(
        blood_group=request.args.get("blood_group"),
        area=request.args.get("area"),
        eligible_only=request.args.get("eligible_only", "").lower() == "true" or None,
        available_only=None if show_all else (request.args.get("available_only", "").lower() == "true" or None),
    )
    with get_session() as session:
        service = SearchService(session)
        results = service.search(
            blood_group=query.blood_group,
            area=query.area,
            eligible_only=query.eligible_only,
            available_only=query.available_only,
        )

        # rank by eligible -> available -> ML prediction, reusing PredictionService
        prediction_service = PredictionService(session)
        for r in results:
            try:
                pred = prediction_service.predict_response_likelihood(r["donor"].id)
                r["prediction_score"] = pred.response_likelihood
            except Exception:
                r["prediction_score"] = 0.0

        results.sort(
            key=lambda r: (
                r["eligibility"].is_eligible,
                r["donor"].is_available,
                r["prediction_score"],
            ),
            reverse=True,
        )

        response = [
            {
                "donor": DonorResponseSchema.model_validate(r["donor"]).model_dump(mode="json"),
                "eligibility": r["eligibility"].model_dump(mode="json"),
                "prediction_score": round(r["prediction_score"], 4),
            }
            for r in results
        ]
        return jsonify(response), 200


# ---------- Prediction Route ----------

@api.route("/prediction/<int:donor_id>", methods=["GET"])
def get_prediction(donor_id: int):
    with get_session() as session:
        service = PredictionService(session)
        result = service.predict_response_likelihood(donor_id)
        return jsonify(result.model_dump(mode="json")), 200


# ---------- Assistant Route ----------

@api.route("/assistant", methods=["POST"])
def query_assistant():
    payload = AssistantQuerySchema(**request.get_json())
    with get_session() as session:
        assistant = Assistant(session)
        result = assistant.handle_query(payload.query)
        return jsonify(result.model_dump(mode="json")), 200


# ---------- Dashboard ----------
@api.route("/dashboard", methods=["GET"])
def get_dashboard_stats():
    """Aggregates existing service/repository data — no new business logic."""
    RARE_GROUPS = {"AB-", "O-", "AB+", "B-"}  # commonly cited rare/low-supply groups

    with get_session() as session:
        donor_service = DonorService(session)
        search_service = SearchService(session)
        donation_repo = DonationRepository(session)

        donors = donor_service.list_donors()
        total_donors = len(donors)

        available = search_service.search(available_only=True)
        available_donors = len(available)

        eligible = search_service.search(eligible_only=True)
        eligible_today = len(eligible)

        rare_count = sum(1 for d in donors if d.blood_group in RARE_GROUPS)
        donations_today = donation_repo.count_donations_today()

        # NEW: chart data, built from data already fetched above — no extra queries
        area_counts = {}
        blood_group_counts = {}
        for d in donors:
            area_counts[d.area] = area_counts.get(d.area, 0) + 1
            blood_group_counts[d.blood_group] = blood_group_counts.get(d.blood_group, 0) + 1

        stats = DashboardStatsSchema(
            total_donors=total_donors,
            eligible_today=eligible_today,
            available_donors=available_donors,
            rare_blood_donors=rare_count,
            donations_today=donations_today,
        )
        payload = stats.model_dump()
        payload["area_counts"] = area_counts
        payload["blood_group_counts"] = blood_group_counts
        payload["not_eligible_today"] = total_donors - eligible_today

        return jsonify(payload), 200


# ---------- Donor Details (full profile) ----------
@api.route("/donors/<int:donor_id>/details", methods=["GET"])
def get_donor_details(donor_id: int):
    with get_session() as session:
        donor_service = DonorService(session)
        donor = donor_service.get_donor(donor_id)
        history = donor_service.get_donation_history(donor_id)
        last_donation_date = donor_service.get_last_donation_date(donor_id)

        eligibility_service = EligibilityService()
        eligibility = eligibility_service.check_eligibility(
            donor_id=donor_id,
            date_of_birth=donor.date_of_birth,
            last_donation_date=last_donation_date,
        )
        # additive: compute days_remaining in the route, without touching the service
        days_remaining = None
        if eligibility.next_eligible_date and not eligibility.is_eligible:
            days_remaining = (eligibility.next_eligible_date - date.today()).days
        eligibility.days_remaining = days_remaining

        details = DonorDetailsResponseSchema(
            donor=DonorResponseSchema.model_validate(donor),
            total_donations=len(history),
            last_donation_date=last_donation_date,
            eligibility=eligibility,
        )
        return jsonify(details.model_dump(mode="json")), 200