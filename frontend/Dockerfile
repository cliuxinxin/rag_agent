# --- Stage 1: Build ---
FROM node:18-alpine as build-stage

WORKDIR /app

# 复制 package.json 并安装依赖
COPY package*.json ./
# 如果在国内构建慢，可以加 registry
# RUN npm config set registry https://registry.npmmirror.com
RUN npm install

# 复制源代码
COPY . .

# 构建生产环境代码 (生成 dist 目录)
RUN npm run build

# --- Stage 2: Serve ---
FROM nginx:stable-alpine as production-stage

# 复制构建好的文件到 Nginx 目录
COPY --from=build-stage /app/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]