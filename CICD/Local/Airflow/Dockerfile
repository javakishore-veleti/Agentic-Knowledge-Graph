# Airflow plus the SDKs the acquisition DAG needs to write to cloud storage.
#
# A built image rather than _PIP_ADDITIONAL_REQUIREMENTS: that variable reinstalls on
# every container start, which turns a restart into a minutes-long download and fails
# entirely without a network. Pinned, so a rebuild months from now produces the same
# image rather than whatever the SDKs have become.
FROM apache/airflow:2.10.2-python3.12

USER airflow
RUN pip install --no-cache-dir \
      "boto3==1.35.36" \
      "azure-storage-blob==12.23.1" \
      "azure-identity==1.19.0" \
      "google-cloud-storage==2.18.2"
