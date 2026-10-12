# GlobaLeaks Docker setup

To run GlobaLeaks using Docker
```bash
 docker run -d --name veridy \
  -p 80:8080 \
  -p 443:8443 \
  -v docker_globaleaks:/var/globaleaks \
  globaleaks/globaleaks:latest