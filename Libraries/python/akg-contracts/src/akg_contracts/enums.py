"""Closed vocabularies. Every one of these encodes a measured finding."""

from __future__ import annotations

from enum import StrEnum


class Env(StrEnum):
    LOCAL = "local"
    AZURE_DEV = "azure-dev"
    AZURE_PROD = "azure-prod"
    # Phase 2 (ADR-002). Present so the enum does not become a breaking change later.
    AWS_DEV = "aws-dev"
    AWS_PROD = "aws-prod"


class Classification(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    PHI = "PHI"


class ConceptRole(StrEnum):
    """How the grounder scored a concept's part in the question (PRD B C5 step 2).

    No model is involved in assigning these; grounding is lexical plus dense span
    matching, because letting a model near an identifier is how ungrounded ids enter
    the pipeline.
    """

    BRIDGE = "bridge"
    FILTER = "filter"
    IGNORE = "ignore"


class CertificationRoute(StrEnum):
    """Why the graph says a candidate is connected to the question.

    This is an *annotation*. It must never remove a candidate: using certification as
    a hard filter halved coverage with no accuracy gain, and it predicts correctness at
    AUROC 0.50 (chance). See ADR-001 and PRD B C2.
    """

    CO_ANNOTATION = "co_annotation"
    ONTOLOGY_ANCESTRY = "ontology_ancestry"
    CITATION_ADJACENCY = "citation_adjacency"
    UNCERTIFIED = "uncertified"


class Disposition(StrEnum):
    ANSWER = "ANSWER"
    REFUSE = "REFUSE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class RefusalReason(StrEnum):
    """Structural gates, then the calibrated gate.

    The five structural gates are vetoes evaluated before the generator is reached, so a
    structural refusal costs no model call. LOW_CONFIDENCE is the only *scored* gate and
    the only one permitted to abstain on a question that reached the generator.
    """

    NO_ENTRY_POINT = "no_entry_point"
    TOO_FEW_CONCEPTS = "too_few_concepts"
    NO_PATH = "no_path"
    NOT_QUOTABLE = "not_quotable"
    ONLY_RETRACTED = "only_retracted"
    NO_EVIDENCE_AS_OF_DATE = "no_evidence_as_of_date"
    LOW_CONFIDENCE = "low_confidence"


class Label(StrEnum):
    YES = "yes"
    NO = "no"
    MAYBE = "maybe"


class ArtifactKind(StrEnum):
    GRAPH = "graph"
    INDEX = "index"
    ONTOLOGY = "ontology"
    CALIBRATION = "calibration"
    CATALOG = "catalog"


class ExecutionModel(StrEnum):
    """How an engine runs work. Determines what the portal may offer (ADR-014).

    Mixing these under one "invoke" is a modelling error: a stream has no run to start,
    and a human process is not finished by compute.
    """

    #: A start, an end, a run id. Invocable.
    TRIGGERED_RUN = "triggered_run"
    #: Always on. Monitored for health and lag, never invoked.
    CONTINUOUS = "continuous"
    #: Instances wait on people, sometimes for days.
    HUMAN_PROCESS = "human_process"


class TechStack(StrEnum):
    """Which engine actually executed a workflow.

    Recorded per execution rather than assumed globally, because one deployment may run
    some workflows on Airflow and others as jobs, and a second cloud adds engines without
    changing any caller (ADR-008).
    """

    # --- triggered runs ---
    AIRFLOW = "airflow"
    CONTAINER_APPS_JOB = "container_apps_job"
    AZURE_FUNCTIONS = "azure_functions"
    AZURE_DATA_FACTORY = "azure_data_factory"
    AZURE_LOGIC_APPS = "azure_logic_apps"
    AWS_STEP_FUNCTIONS = "aws_step_functions"
    AWS_LAMBDA = "aws_lambda"
    AWS_EMR = "aws_emr"
    AWS_GLUE = "aws_glue"
    AWS_BATCH = "aws_batch"
    DATABRICKS_JOB = "databricks_job"
    CUSTOM_API = "custom_api"

    # --- continuous: no discrete run ---
    AZURE_KAFKA_CONSUMER = "azure_kafka_consumer"
    AWS_KAFKA_CONSUMER = "aws_kafka_consumer"
    AWS_KINESIS = "aws_kinesis"
    AZURE_EVENT_HUBS = "azure_event_hubs"
    SPARK_STREAMING = "spark_streaming"

    # --- human process ---
    BPMN_CAMUNDA = "bpmn_camunda"
    BPMN_FLOWABLE = "bpmn_flowable"

    @property
    def execution_model(self) -> "ExecutionModel":
        if self in _CONTINUOUS:
            return ExecutionModel.CONTINUOUS
        if self in _HUMAN:
            return ExecutionModel.HUMAN_PROCESS
        return ExecutionModel.TRIGGERED_RUN

    @property
    def invocable(self) -> bool:
        """Only a triggered run can be invoked. Invoking a stream would log a PENDING
        execution that never completes."""
        return self.execution_model is ExecutionModel.TRIGGERED_RUN


_CONTINUOUS = {
    TechStack.AZURE_KAFKA_CONSUMER, TechStack.AWS_KAFKA_CONSUMER, TechStack.AWS_KINESIS,
    TechStack.AZURE_EVENT_HUBS, TechStack.SPARK_STREAMING,
}
_HUMAN = {TechStack.BPMN_CAMUNDA, TechStack.BPMN_FLOWABLE}


class WorkflowStatus(StrEnum):
    # Written before the engine is invoked, so a submit that never reached the engine is
    # visible as PENDING with no wf_ref_id rather than absent entirely.
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in {
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }
