"""Production DynamoDB single-table repository implementation for CareThread.

Implements the single-table design specified in Section 4.1:
PK = PATIENT#<patient_id>
SK patterns:
- PROFILE
- DOC#<iso_ts>#<doc_id>
- MED#<normalised_name>
- LAB#<iso_ts>#<analyte>
- DIAG#<code_or_slug>
- PLAN#<day_index>#<slot>
- ALERT#<iso_ts>
"""

import os
from datetime import datetime, timezone
from typing import Any, List, Optional
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from carethread.shared.schemas.patient import Patient
from carethread.shared.schemas.document import Document
from carethread.shared.schemas.medication import Medication
from carethread.shared.schemas.lab_result import LabResult
from carethread.shared.schemas.diagnosis import Diagnosis
from carethread.shared.schemas.plan_entry import PlanEntry
from carethread.shared.schemas.alert_rule import FiredAlert
from carethread.shared.schemas.api import PatientRecordResponse

from .interfaces import PatientRepositoryInterface
from .serializer import to_dynamodb_friendly, from_dynamodb_friendly
from .exceptions import (
    DatabaseError,
    PatientNotFoundError,
    DocumentNotFoundError,
    EntityNotFoundError,
    MissingProvenanceError,
    InvalidPatientIdError,
)


class DynamoDBPatientRepository(PatientRepositoryInterface):
    """DynamoDB single-table implementation of PatientRepositoryInterface."""

    def __init__(
        self,
        table_name: Optional[str] = None,
        table_resource: Optional[Any] = None,
        region_name: Optional[str] = None
    ):
        self.table_name = table_name or os.environ.get("TABLE_NAME", "carethread")
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        if table_resource:
            self._table = table_resource
        else:
            dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
            self._table = dynamodb.Table(self.table_name)

    def _validate_patient_id(self, patient_id: str) -> str:
        if not patient_id or not isinstance(patient_id, str) or not patient_id.strip():
            raise InvalidPatientIdError("patient_id must be a non-empty string")
        return patient_id.strip()

    def _query_all(self, **kwargs: Any) -> List[dict]:
        """Query the table, following LastEvaluatedKey to completion.

        A single Query page caps at 1 MB. A patient with a 7-day plan, a
        document history and a full lab panel can exceed that, and an
        unpaginated read would silently return a truncated record -- the
        canonical context must never be partial.
        """
        items: List[dict] = []
        last_key: Optional[dict] = None
        while True:
            page_kwargs = dict(kwargs)
            if last_key:
                page_kwargs["ExclusiveStartKey"] = last_key
            response = self._table.query(**page_kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                return items

    def _validate_provenance(self, entity_name: str, entity: object) -> None:
        """Enforce the one invariant: extracted clinical entities must possess valid provenance."""
        provenance = getattr(entity, "provenance", None)
        if provenance is None:
            raise MissingProvenanceError(f"Cannot persist {entity_name} without valid provenance")
        source = getattr(provenance, "source", None)
        if source is None:
            raise MissingProvenanceError(f"Cannot persist {entity_name}: provenance.source is missing")

    def create_patient(self, patient: Patient) -> Patient:
        self._validate_patient_id(patient.patient_id)
        item = to_dynamodb_friendly(patient)
        item["PK"] = patient.pk
        item["SK"] = patient.sk
        try:
            self._table.put_item(Item=item)
            return patient
        except ClientError as e:
            raise DatabaseError(f"Failed to create patient: {e}") from e

    def get_patient(self, patient_id: str) -> Optional[Patient]:
        self._validate_patient_id(patient_id)
        try:
            response = self._table.get_item(
                Key={"PK": f"PATIENT#{patient_id}", "SK": "PROFILE"}
            )
            item = response.get("Item")
            if not item:
                return None
            clean_item = from_dynamodb_friendly(item)
            return Patient.model_validate(clean_item)
        except ClientError as e:
            raise DatabaseError(f"Failed to get patient: {e}") from e

    def update_patient(self, patient: Patient) -> Patient:
        self._validate_patient_id(patient.patient_id)
        # Verify exists
        existing = self.get_patient(patient.patient_id)
        if not existing:
            raise PatientNotFoundError(f"Patient {patient.patient_id} not found")
        item = to_dynamodb_friendly(patient)
        item["PK"] = patient.pk
        item["SK"] = patient.sk
        try:
            self._table.put_item(Item=item)
            return patient
        except ClientError as e:
            raise DatabaseError(f"Failed to update patient: {e}") from e

    def create_document(self, document: Document) -> Document:
        self._validate_patient_id(document.patient_id)
        item = to_dynamodb_friendly(document)
        item["PK"] = document.pk
        item["SK"] = document.sk
        # GSI1 for processing documents spinner
        item["GSI1PK"] = document.status.value if hasattr(document.status, "value") else str(document.status)
        item["GSI1SK"] = document.pk
        try:
            self._table.put_item(Item=item)
            return document
        except ClientError as e:
            raise DatabaseError(f"Failed to create document: {e}") from e

    def get_document(self, patient_id: str, doc_id: str) -> Optional[Document]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("DOC#")
            )
            for raw_item in items:
                clean = from_dynamodb_friendly(raw_item)
                if clean.get("doc_id") == doc_id:
                    return Document.model_validate(clean)
            return None
        except ClientError as e:
            raise DatabaseError(f"Failed to get document: {e}") from e

    def list_documents(self, patient_id: str) -> List[Document]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("DOC#")
            )
            docs = [Document.model_validate(from_dynamodb_friendly(it)) for it in items]
            return sorted(docs, key=lambda d: d.created_at)
        except ClientError as e:
            raise DatabaseError(f"Failed to list documents: {e}") from e

    def update_document(self, document: Document) -> Document:
        """Advance a document's lifecycle with a targeted, non-destructive update."""
        self._validate_patient_id(document.patient_id)
        pages = document.pages if document.pages is not None else []
        try:
            self._table.update_item(
                Key={"PK": document.pk, "SK": document.sk},
                UpdateExpression=(
                    "SET #s = :status, #t = :type, #p = :pages, "
                    "updated_at = :updated_at, error_reason = :error_reason"
                ),
                # status/type/pages are DynamoDB reserved words.
                ExpressionAttributeNames={"#s": "status", "#t": "type", "#p": "pages"},
                ExpressionAttributeValues=to_dynamodb_friendly(
                    {
                        ":status": document.status.value,
                        ":type": document.type.value,
                        ":pages": pages,
                        ":updated_at": document.updated_at,
                        ":error_reason": document.error_reason,
                    }
                ),
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
            )
            return document
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise DocumentNotFoundError(
                    f"Document {document.doc_id} not found for patient {document.patient_id}"
                ) from e
            raise DatabaseError(f"Failed to update document: {e}") from e

    def update_entity_field(
        self,
        patient_id: str,
        sk: str,
        field: str,
        value: Any,
        confirm_provenance: bool = True,
    ) -> dict:
        """Targeted single-field update, leaving every other attribute untouched."""
        self._validate_patient_id(patient_id)
        pk = f"PATIENT#{patient_id}"

        update_parts = ["#f = :value", "updated_at = :updated_at"]
        names = {"#f": field}
        values = {
            ":value": value,
            ":updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if confirm_provenance:
            # Only rewrites the nested status; the source citation is untouched.
            update_parts.append("#prov.#st = :confirmed")
            names["#prov"] = "provenance"
            names["#st"] = "status"
            values[":confirmed"] = "confirmed"

        def _write(expression: str, attr_names: dict, attr_values: dict) -> dict:
            return self._table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression="SET " + expression,
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=to_dynamodb_friendly(attr_values),
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
                ReturnValues="ALL_NEW",
            )

        try:
            try:
                response = _write(", ".join(update_parts), names, values)
            except ClientError as e:
                # Entities without a provenance map (a patient PROFILE) cannot
                # take the nested status write; retry with the field alone.
                code = e.response.get("Error", {}).get("Code")
                if not confirm_provenance or code != "ValidationException":
                    raise
                response = _write(
                    "#f = :value, updated_at = :updated_at",
                    {"#f": field},
                    {":value": value, ":updated_at": values[":updated_at"]},
                )
            return from_dynamodb_friendly(response.get("Attributes", {}))
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise EntityNotFoundError(
                    f"Record entity with SK '{sk}' not found for patient '{patient_id}'"
                ) from e
            raise DatabaseError(f"Failed to update {sk}.{field}: {e}") from e

    def create_medication(self, patient_id: str, medication: Medication) -> Medication:
        self._validate_patient_id(patient_id)
        self._validate_provenance("Medication", medication)
        item = to_dynamodb_friendly(medication)
        item["PK"] = medication.pk(patient_id)
        item["SK"] = medication.sk
        try:
            self._table.put_item(Item=item)
            return medication
        except ClientError as e:
            raise DatabaseError(f"Failed to create medication: {e}") from e

    def get_medications(self, patient_id: str) -> List[Medication]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("MED#")
            )
            return [Medication.model_validate(from_dynamodb_friendly(it)) for it in items]
        except ClientError as e:
            raise DatabaseError(f"Failed to get medications: {e}") from e

    def create_lab_result(self, patient_id: str, lab_result: LabResult, timestamp: Optional[str] = None) -> LabResult:
        self._validate_patient_id(patient_id)
        self._validate_provenance("LabResult", lab_result)
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        # Stamping the timestamp makes the serialised `sk` the real storage key.
        lab_result = lab_result.model_copy(update={"reported_at": ts})
        item = to_dynamodb_friendly(lab_result)
        item["PK"] = lab_result.pk(patient_id)
        item["SK"] = lab_result.sk_for(ts)
        try:
            self._table.put_item(Item=item)
            return lab_result
        except ClientError as e:
            raise DatabaseError(f"Failed to create lab result: {e}") from e

    def get_lab_results(self, patient_id: str) -> List[LabResult]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("LAB#")
            )
            return [LabResult.model_validate(from_dynamodb_friendly(it)) for it in items]
        except ClientError as e:
            raise DatabaseError(f"Failed to get lab results: {e}") from e

    def create_diagnosis(self, patient_id: str, diagnosis: Diagnosis) -> Diagnosis:
        self._validate_patient_id(patient_id)
        self._validate_provenance("Diagnosis", diagnosis)
        item = to_dynamodb_friendly(diagnosis)
        item["PK"] = diagnosis.pk(patient_id)
        item["SK"] = diagnosis.sk
        try:
            self._table.put_item(Item=item)
            return diagnosis
        except ClientError as e:
            raise DatabaseError(f"Failed to create diagnosis: {e}") from e

    def get_diagnoses(self, patient_id: str) -> List[Diagnosis]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("DIAG#")
            )
            return [Diagnosis.model_validate(from_dynamodb_friendly(it)) for it in items]
        except ClientError as e:
            raise DatabaseError(f"Failed to get diagnoses: {e}") from e

    def create_plan_entry(self, patient_id: str, plan_entry: PlanEntry) -> PlanEntry:
        self._validate_patient_id(patient_id)
        self._validate_provenance("PlanEntry", plan_entry)
        item = to_dynamodb_friendly(plan_entry)
        item["PK"] = plan_entry.pk(patient_id)
        item["SK"] = plan_entry.sk
        try:
            self._table.put_item(Item=item)
            return plan_entry
        except ClientError as e:
            raise DatabaseError(f"Failed to create plan entry: {e}") from e

    def get_plan_entries(self, patient_id: str) -> List[PlanEntry]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("PLAN#")
            )
            entries = [PlanEntry.model_validate(from_dynamodb_friendly(it)) for it in items]
            return sorted(entries, key=lambda e: (e.day_index, e.slot.value))
        except ClientError as e:
            raise DatabaseError(f"Failed to get plan entries: {e}") from e

    def update_plan_entry_done(
        self,
        patient_id: str,
        day_index: int,
        slot: str,
        done: bool = True,
        completed_at: Optional[str] = None
    ) -> PlanEntry:
        self._validate_patient_id(patient_id)
        slot_str = slot.value if hasattr(slot, "value") else str(slot)
        pk = f"PATIENT#{patient_id}"
        sk = f"PLAN#{day_index}#{slot_str}"
        ts = completed_at or datetime.now(timezone.utc).isoformat()

        try:
            response = self._table.update_item(
                Key={"PK": pk, "SK": sk},
                UpdateExpression="SET #done = :done, #completed_at = :completed_at",
                ExpressionAttributeNames={"#done": "done", "#completed_at": "completed_at"},
                ExpressionAttributeValues={":done": done, ":completed_at": ts},
                ConditionExpression="attribute_exists(PK) AND attribute_exists(SK)",
                ReturnValues="ALL_NEW"
            )
            attributes = response.get("Attributes", {})
            return PlanEntry.model_validate(from_dynamodb_friendly(attributes))
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise EntityNotFoundError(f"PlanEntry for day {day_index} slot {slot_str} not found") from e
            raise DatabaseError(f"Failed to update plan entry done status: {e}") from e

    def create_alert(self, patient_id: str, alert: FiredAlert) -> FiredAlert:
        self._validate_patient_id(patient_id)
        item = to_dynamodb_friendly(alert)
        item["PK"] = alert.pk(patient_id)
        item["SK"] = alert.sk
        try:
            self._table.put_item(Item=item)
            return alert
        except ClientError as e:
            raise DatabaseError(f"Failed to create alert: {e}") from e

    def get_alerts(self, patient_id: str) -> List[FiredAlert]:
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}") & Key("SK").begins_with("ALERT#")
            )
            alerts = [FiredAlert.model_validate(from_dynamodb_friendly(it)) for it in items]
            return sorted(alerts, key=lambda a: a.fired_at, reverse=True)
        except ClientError as e:
            raise DatabaseError(f"Failed to get alerts: {e}") from e

    def get_patient_context(self, patient_id: str) -> PatientRecordResponse:
        """The canonical single query Query(PK = PATIENT#<id>) loading all patient context in one roundtrip."""
        self._validate_patient_id(patient_id)
        try:
            items = self._query_all(
                KeyConditionExpression=Key("PK").eq(f"PATIENT#{patient_id}")
            )
            raw_items = items

            patient: Optional[Patient] = None
            docs: List[Document] = []
            meds: List[Medication] = []
            labs: List[LabResult] = []
            diags: List[Diagnosis] = []
            plan: List[PlanEntry] = []
            alerts: List[FiredAlert] = []

            for raw_item in raw_items:
                data = from_dynamodb_friendly(raw_item)
                sk = data.get("SK", "")
                if sk == "PROFILE":
                    patient = Patient.model_validate(data)
                elif sk.startswith("DOC#"):
                    docs.append(Document.model_validate(data))
                elif sk.startswith("MED#"):
                    meds.append(Medication.model_validate(data))
                elif sk.startswith("LAB#"):
                    labs.append(LabResult.model_validate(data))
                elif sk.startswith("DIAG#"):
                    diags.append(Diagnosis.model_validate(data))
                elif sk.startswith("PLAN#"):
                    plan.append(PlanEntry.model_validate(data))
                elif sk.startswith("ALERT#"):
                    alerts.append(FiredAlert.model_validate(data))

            return PatientRecordResponse(
                patient=patient,
                documents=sorted(docs, key=lambda d: d.created_at),
                diagnoses=diags,
                medications=meds,
                lab_results=labs,
                plan_entries=sorted(plan, key=lambda e: (e.day_index, e.slot.value)),
                alerts=sorted(alerts, key=lambda a: a.fired_at, reverse=True)
            )
        except ClientError as e:
            raise DatabaseError(f"Failed to query patient context: {e}") from e
