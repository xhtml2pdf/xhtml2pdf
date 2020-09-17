FROM ubuntu:xenial

RUN mkdir code
WORKDIR /code

RUN apt-get update && \
    apt-get install -y imagemagick ghostscript python3

RUN apt-get update && \
    apt-get install -y python3-pip

#RUN apt-get update && \
    #apt-get install -y vim

RUN sed -i 's#<policy domain="coder" rights="none" pattern="PDF" />#<policy domain="coder" rights="read|write" pattern="PDF" />#' /etc/ImageMagick-6/policy.xml

RUN python3 -m pip install --upgrade pip

COPY requirements.txt /code/
RUN python3 -m pip install --no-cache-dir -r requirements.txt

RUN apt-get -y autoremove && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /code/

RUN python3 setup.py install

CMD [ "python3", "testrender/testrender.py" ]
