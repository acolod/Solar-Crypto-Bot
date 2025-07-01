
FROM python:3.11-slim AS frontend-builder

RUN apt-get update && apt-get install -y --no-install-recommends     curl     ca-certificates     && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - &&     apt-get install -y nodejs &&     npm install -g pnpm &&     npm cache clean --force

WORKDIR /deployment/app

COPY app/package.json app/pnpm-lock.yaml ./
RUN pnpm install

COPY app/ ./
RUN pnpm build

FROM python:3.10-slim
RUN apt-get update && apt-get install -y --no-install-recommends     curl     ca-certificates     libpq5     nginx     && apt-get clean && rm -rf /var/lib/apt/lists/*

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /deployment
RUN mkdir -p /deployment/app /deployment/services

COPY --from=frontend-builder /deployment/app/dist /deployment/app/dist
COPY services /deployment/services
RUN cd /deployment/services && uv add pydantic httpx httpcore h11 pyjwt python-dotenv fastapi uvicorn requests beautifulsoup4 psycopg-pool psycopg boto3 python-multipart loguru

# Create main nginx.conf with prerender maps
RUN echo "user www-data;\n\
worker_processes auto;\n\
pid /run/nginx.pid;\n\
\n\
events {\n\
    worker_connections 768;\n\
}\n\
\n\
http {\n\
    sendfile on;\n\
    tcp_nopush on;\n\
    tcp_nodelay on;\n\
    keepalive_timeout 65;\n\
    types_hash_max_size 2048;\n\
\n\
    include /etc/nginx/mime.types;\n\
    default_type application/octet-stream;\n\
\n\
    access_log /var/log/nginx/access.log;\n\
    error_log /var/log/nginx/error.log;\n\
\n\
    gzip on;\n\
\n\
    # Prerender.io maps\n\
    map \$http_user_agent \$prerender_ua {\n\
        default       0;\n\
        \"~*Prerender\" 0;\n\
        \"~*googlebot\"                               1;\n\
        \"~*yahoo! slurp\"                           1;\n\
        \"~*bingbot\"                                 1;\n\
        \"~*yandex\"                                  1;\n\
        \"~*baiduspider\"                             1;\n\
        \"~*facebookexternalhit\"                     1;\n\
        \"~*twitterbot\"                              1;\n\
        \"~*rogerbot\"                                1;\n\
        \"~*linkedinbot\"                             1;\n\
        \"~*embedly\"                                 1;\n\
        \"~*quora link preview\"                      1;\n\
        \"~*showyoubot\"                              1;\n\
        \"~*outbrain\"                                1;\n\
        \"~*pinterest\\/0\\.\"                          1;\n\
        \"~*developers.google.com\\/\\+\\/web\\/snippet\" 1;\n\
        \"~*slackbot\"                                1;\n\
        \"~*vkshare\"                                 1;\n\
        \"~*w3c_validator\"                           1;\n\
        \"~*redditbot\"                               1;\n\
        \"~*applebot\"                                1;\n\
        \"~*whatsapp\"                                1;\n\
        \"~*flipboard\"                               1;\n\
        \"~*tumblr\"                                  1;\n\
        \"~*bitlybot\"                                1;\n\
        \"~*skypeuripreview\"                         1;\n\
        \"~*nuzzel\"                                  1;\n\
        \"~*discordbot\"                              1;\n\
        \"~*google page speed\"                       1;\n\
        \"~*qwantify\"                                1;\n\
        \"~*pinterestbot\"                            1;\n\
        \"~*bitrix link preview\"                     1;\n\
        \"~*xing-contenttabreceiver\"                 1;\n\
        \"~*chrome-lighthouse\"                       1;\n\
        \"~*telegrambot\"                             1;\n\
        \"~*google-inspectiontool\"                   1;\n\
        \"~*petalbot\"                                1;\n\
    }\n\
\n\
    map \$args \$prerender_args {\n\
        default \$prerender_ua;\n\
        \"~(^|&)_escaped_fragment_=\" 1;\n\
    }\n\
\n\
    map \$http_x_prerender \$x_prerender {\n\
        default \$prerender_args;\n\
        \"1\"     0;\n\
    }\n\
\n\
    map \$uri \$prerender {\n\
        default \$x_prerender;\n\
        \"~*\\.(js|css|xml|less|png|jpg|jpeg|gif|pdf|txt|ico|rss|zip|mp3|rar|exe|wmv|doc|avi|ppt|mpg|mpeg|tif|wav|mov|psd|ai|xls|mp4|m4a|swf|dat|dmg|iso|flv|m4v|torrent|ttf|woff|woff2|svg|eot)\" 0;\n\
    }\n\
\n\
    include /etc/nginx/conf.d/*.conf;\n\
    include /etc/nginx/sites-enabled/*;\n\
}" > /etc/nginx/nginx.conf

# Create server block configuration
RUN echo "server { \
    listen 8000; \
    root /deployment/app/dist; \
    client_max_body_size 100M; \
    \
    # API routes - not prerendered \
    location /api/ { \
        proxy_pass http://localhost:5000; \
        proxy_set_header Host \$host; \
        proxy_set_header X-Real-IP \$remote_addr; \
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; \
    } \
    \
    # Main location block with prerender support \
    location / { \
        if (\$prerender = 1) { \
            rewrite (.*) /prerenderio last; \
        } \
        \
        try_files \$uri \$uri/ /index.html; \
    } \
    \
    # Cache control for static assets \
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ { \
        expires 1y; \
        add_header Cache-Control \"public, immutable\"; \
    } \
    \
    # Prerender.io proxy \
    location /prerenderio { \
        if (\$prerender = 0) { \
            return 404; \
        } \
        \
        proxy_set_header X-Prerender-Token PRERENDER_TOKEN_PLACEHOLDER; \
        proxy_set_header X-Prerender-Int-Type Nginx_Rev_Proxy; \
        \
        proxy_hide_header Cache-Control; \
        add_header Cache-Control \"private,max-age=600,must-revalidate\"; \
        \
        # Resolve using Google DNS \
        resolver 8.8.8.8 8.8.4.4; \
        set \$prerender_host \"service.prerender.io\"; \
        proxy_pass https://\$prerender_host; \
        rewrite .* /\$scheme://\$host\$request_uri? break; \
    } \
}" > /etc/nginx/sites-available/default

RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Check if PRERENDER_TOKEN is set\n\
if [ -z "$PRERENDER_TOKEN" ]; then\n\
  echo "WARNING: PRERENDER_TOKEN environment variable is not set!"\n\
  echo "Prerender.io will not work without a valid token."\n\
  export PRERENDER_TOKEN="DUMMY_TOKEN"\n\
fi\n\
\n\
# Replace the token placeholder in nginx config\n\
sed -i "s/PRERENDER_TOKEN_PLACEHOLDER/$PRERENDER_TOKEN/g" /etc/nginx/sites-available/default\n\
\n\
# Start backend API server\n\
cd /deployment/services\n\
if [ -f "api/routes.py" ]; then\n\
  echo "Starting backend API server..."\n\
  uv run uvicorn api.routes:app --host 0.0.0.0 --port 5000 &\n\
fi\n\
\n\
# Test nginx configuration\n\
echo "Testing nginx configuration..."\n\
nginx -t\n\
\n\
# Start nginx in foreground\n\
echo "Starting nginx..."\n\
nginx -g "daemon off;"\n\
' > /deployment/start.sh && \
chmod +x /deployment/start.sh

WORKDIR /deployment
EXPOSE 8000
CMD ["/deployment/start.sh"]
