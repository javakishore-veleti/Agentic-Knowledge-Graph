--liquibase formatted sql

--changeset akg:007-workflow-engines splitStatements:false endDelimiter:\n/
--comment workflow engines
--rollback empty

-- Engines and execution models for the workflow master (ADR-014).
--
-- Three execution models, because "invoke" does not mean the same thing for all of them:
--
--   triggered_run     Airflow, Step Functions, EMR, Data Factory, Lambda, Container Apps
--                     Jobs. A start, an end, a run id. This is what invoke means.
--   continuous        Kinesis, Kafka consumers, Structured Streaming. No run at all --
--                     always on. Asking "did it complete" is meaningless; the questions
--                     are "is it healthy" and "how far behind". Invoking one would fill
--                     the exec log with PENDING rows that never complete.
--   human_process     BPMN (Camunda, Flowable). Instances wait on people, sometimes for
--                     days; completion is not driven by compute.
ALTER TABLE catalog.workflow
    ADD COLUMN IF NOT EXISTS execution_model text NOT NULL DEFAULT 'triggered_run';

ALTER TABLE catalog.workflow DROP CONSTRAINT IF EXISTS workflow_exec_model_ck;
ALTER TABLE catalog.workflow
    ADD CONSTRAINT workflow_exec_model_ck
    CHECK (execution_model IN ('triggered_run', 'continuous', 'human_process'));

-- default_tech_stack had no constraint: the column would have accepted any string, and a
-- typo would surface as a portal offering a button for an engine no adapter implements.
ALTER TABLE catalog.workflow DROP CONSTRAINT IF EXISTS workflow_tech_stack_ck;
ALTER TABLE catalog.workflow
    ADD CONSTRAINT workflow_tech_stack_ck CHECK (default_tech_stack IN (
        -- triggered runs
        'airflow', 'container_apps_job', 'azure_functions', 'azure_data_factory',
        'azure_logic_apps', 'aws_step_functions', 'aws_lambda', 'aws_emr', 'aws_glue',
        'aws_batch', 'databricks_job', 'custom_api',
        -- continuous
        'azure_kafka_consumer', 'aws_kafka_consumer', 'aws_kinesis',
        'azure_event_hubs', 'spark_streaming',
        -- human process
        'bpmn_camunda', 'bpmn_flowable'
    ));

-- Same closed set on the execution log, which was also unconstrained.
ALTER TABLE orchestration.wf_exec_log DROP CONSTRAINT IF EXISTS wf_exec_log_tech_ck;
ALTER TABLE orchestration.wf_exec_log
    ADD CONSTRAINT wf_exec_log_tech_ck CHECK (tech_stack IN (
        'airflow', 'container_apps_job', 'azure_functions', 'azure_data_factory',
        'azure_logic_apps', 'aws_step_functions', 'aws_lambda', 'aws_emr', 'aws_glue',
        'aws_batch', 'databricks_job', 'custom_api',
        'azure_kafka_consumer', 'aws_kafka_consumer', 'aws_kinesis',
        'azure_event_hubs', 'spark_streaming',
        'bpmn_camunda', 'bpmn_flowable'
    ));

-- A continuous engine has no discrete run, so it must not be attached as something the
-- portal offers an "Invoke" button for. Enforced rather than left to the UI, because the
-- UI is not the only writer.
CREATE OR REPLACE VIEW catalog.workflow_invocable AS
SELECT workflow_id, code, name, domain, sub_domain, default_tech_stack, execution_model,
       params_json, purpose, is_active, tenant_id
FROM catalog.workflow
WHERE is_active AND execution_model = 'triggered_run';

-- Continuous workflows: monitored, not invoked.
CREATE OR REPLACE VIEW catalog.workflow_continuous AS
SELECT workflow_id, code, name, domain, sub_domain, default_tech_stack, is_active, tenant_id
FROM catalog.workflow
WHERE execution_model = 'continuous';

-- An execution logged against a continuous engine is a modelling error: those do not have
-- runs. Non-empty means something is writing exec rows for a stream.
CREATE OR REPLACE VIEW catalog.wf_exec_log_model_mismatch AS
SELECT e.exec_id, e.workflow, e.tech_stack, w.execution_model
FROM orchestration.wf_exec_log e
JOIN catalog.workflow w ON w.code = e.workflow
WHERE w.execution_model = 'continuous';
