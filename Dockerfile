FROM docker.repo.splunkdev.net/ci-cd/ci-container:python-3.7-buster

WORKDIR /biased-lang

# Install basic requirements
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  wget \
  make \
  git \
  ripgrep \
  && rm -rf /var/lib/apt/lists/* \
  && apt-get clean all

# copy dependency file first for Dockerfile caching
COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .
