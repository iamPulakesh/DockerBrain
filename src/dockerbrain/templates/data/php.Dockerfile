FROM php:8.3-apache

# Enable Apache mod_rewrite
RUN a2enmod rewrite

# Install required extensions
RUN apt-get update && apt-get install -y \
    libzip-dev \
    zip \
    && docker-php-ext-install pdo_mysql zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /var/www/html

COPY . .

# Set appropriate permissions
RUN chown -R www-data:www-data /var/www/html

EXPOSE 80

CMD ["apache2-foreground"]
