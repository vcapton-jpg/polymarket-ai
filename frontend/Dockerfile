FROM node:20-alpine AS builder

# Required by `node-gyp` for native deps that ship without arm64 prebuilds
# on alpine (utf-8-validate, bufferutil). Without these, `npm install`
# fails with "gyp ERR! find Python" on arm64 builds.
RUN apk add --no-cache python3 make g++

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]