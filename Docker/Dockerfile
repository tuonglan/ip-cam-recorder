FROM tuonglan/ffmpeg:4.3
MAINTAINER Lan Do (tuonglan7777777@gmail.com)

# Install python3
RUN apt-get update && apt-get install -y python3 python3-dev python3-pip

# Copy files to location
COPY Docker/requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt
COPY main.py ffmpeg_recorder.py logger.py slack_bot.py /opt/ip-cam-recorder/

WORKDIR /opt/ip-cam-recorder

ENTRYPOINT ["/bin/bash", "-c"]

