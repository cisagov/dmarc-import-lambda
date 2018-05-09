FROM lambci/lambda:build-python3.6
MAINTAINER Shane Frasier <jeremy.frasier@beta.dhs.gov>

# We need wget to download the public suffix list
# RUN yum -q -y install wget

COPY build.sh .
COPY lambda_handler.py .

ENTRYPOINT ["./build.sh"]
