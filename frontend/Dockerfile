# --- AŞAMA 1: Build ---
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
RUN npm install --legacy-peer-deps @capacitor/core @capacitor/haptics
COPY . .
RUN npm run build

# --- AŞAMA 2: Nginx ---
FROM nginx:alpine
# Kendi yazdığımız konfigürasyonu içeri atıyoruz
COPY default.conf /etc/nginx/conf.d/default.conf
# Build dosyalarını kopyalıyoruz
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
