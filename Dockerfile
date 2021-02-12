FROM python:3.7-slim
MAINTAINER Adam Kloboucnik <ak@blockcollider.org>

RUN apt-get update && apt-get install -y \
  curl \
  node-pre-gyp \
  build-essential \
  git \
  dumb-init \
  docker.io

RUN curl -sL https://deb.nodesource.com/setup_10.x | bash - \
&& apt-get install -y nodejs

RUN pip install poetry
RUN curl -o- -L https://yarnpkg.com/install.sh | bash -s -- --version 1.19.0 \
    && export PATH=$HOME/.yarn/bin:$PATH
ENV PATH "/root/.yarn/bin:$PATH"

RUN mkdir /src && mkdir -p /src/mm_bot/exchange/maker
# don't change this src
WORKDIR /src

COPY poetry.lock .
COPY pyproject.toml .
RUN cd /src && poetry install
COPY ./mm_bot/exchange/maker/package.json /src/mm_bot/exchange/maker
COPY ./mm_bot/exchange/maker/yarn.lock /src/mm_bot/exchange/maker
RUN cd /src/mm_bot/exchange/maker && yarn

COPY . .

ENTRYPOINT ["dumb-init", "--"]
CMD ["bash"]
