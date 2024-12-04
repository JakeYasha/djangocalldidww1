FROM python:3.9-slim

# Install system dependencies including PulseAudio
RUN apt-get update && apt-get install -y \
    python3-dev \
    build-essential \
    libssl-dev \
    python3-pip \
    git \
    pulseaudio \
    alsa-utils \
    libasound2-dev \
    wget \
    libpulse-dev \
    portaudio19-dev \
    ffmpeg \
    libavcodec-extra \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Download and install PJSIP
WORKDIR /tmp
RUN wget https://github.com/pjsip/pjproject/archive/refs/tags/2.14.1.tar.gz && \
    tar -xf 2.14.1.tar.gz && \
    cd pjproject-2.14.1 && \
    export CFLAGS="$CFLAGS -fPIC -DPJMEDIA_AUDIO_DEV_HAS_PORTAUDIO=1" && \
    ./configure --enable-shared \
                --with-external-pa \
                --enable-ext-sound \
                --enable-ice \
                --with-ssl \
                --disable-speex-codec \
                --disable-speex-aec \
                --disable-l16-codec \
                --disable-gsm-codec \
                --disable-g722-codec \
                --disable-g7221-codec \
                --disable-ilbc-codec && \
    make dep && make clean && make && make install && \
    ldconfig && \
    cd pjsip-apps/src && \
    git clone https://github.com/mgwilliams/python3-pjsip.git && \
    cd python3-pjsip && \
    python3 setup.py build && \
    python3 setup.py install

# Устанавливаем часовой пояс
RUN apt-get update && apt-get install -y tzdata
ENV TZ=Europe/Riga
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create a non-root user
RUN useradd -m appuser && \
    mkdir -p /home/appuser/app && \
    chown -R appuser:appuser /home/appuser

# Set up PulseAudio configuration
RUN mkdir -p /etc/pulse
COPY pulse-client.conf /etc/pulse/client.conf
RUN mkdir -p /home/appuser/.config/pulse && \
    cp /etc/pulse/client.conf /home/appuser/.config/pulse/ && \
    chown -R appuser:appuser /home/appuser/.config

# Set up ALSA configuration
RUN echo "pcm.!default {\n\
    type pulse\n\
    fallback \"sysdefault\"\n\
    hint {\n\
        show on\n\
        description \"PulseAudio Sound Server\"\n\
    }\n\
}\n\
\n\
ctl.!default {\n\
    type pulse\n\
    fallback \"sysdefault\"\n\
}\n\
\n\
pcm.pulse {\n\
    type pulse\n\
}\n\
\n\
ctl.pulse {\n\
    type pulse\n\
}" > /etc/asound.conf

# Copy application code and set permissions
WORKDIR /home/appuser/app
COPY . .
RUN chown -R appuser:appuser /home/appuser/app && \
    mkdir -p recordings && \
    chown -R appuser:appuser recordings

# Set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chown appuser:appuser /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/home/appuser/app
ENV DJANGO_SETTINGS_MODULE=phone_tracker.settings

# Expose port
EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
