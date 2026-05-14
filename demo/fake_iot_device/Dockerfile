FROM alpine:3.20

RUN apk add --no-cache openssh-server \
    && adduser -D -s /bin/sh iot \
    && echo "iot:raspberrypi" | chpasswd \
    && mkdir -p /var/run/sshd

COPY sshd_config /etc/ssh/sshd_config
COPY banner.txt /etc/banner.txt
COPY entrypoint.sh /entrypoint.sh

RUN chmod 0755 /entrypoint.sh

EXPOSE 2222

ENTRYPOINT ["/entrypoint.sh"]
