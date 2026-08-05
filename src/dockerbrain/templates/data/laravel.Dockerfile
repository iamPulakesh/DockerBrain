FROM php:8.3-apache

RUN a2enmod rewrite && \
    apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev libzip-dev unzip && \
    docker-php-ext-install pdo_mysql gd zip && \
    rm -rf /var/lib/apt/lists/*

COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

COPY . .
RUN composer install --no-dev --optimize-autoloader

RUN chown -R www-data:www-data storage bootstrap/cache

ENV APACHE_DOCUMENT_ROOT=/var/www/html/public
RUN sed -ri 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/000-default.conf

EXPOSE 80

CMD ["apache2-foreground"]
