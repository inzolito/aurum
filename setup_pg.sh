#!/bin/bash
set -e

echo "Updating packages and installing PostgreSQL..."
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib

echo "Configuring postgresql.conf to listen on all addresses..."
PG_CONF=$(find /etc/postgresql/ -name "postgresql.conf" | head -n 1)
if grep -q "^listen_addresses" "$PG_CONF"; then
    sudo sed -i "s/^listen_addresses.*/listen_addresses = '*'/g" "$PG_CONF"
else
    sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" "$PG_CONF"
fi

echo "Configuring pg_hba.conf to allow Surface IP..."
PG_HBA=$(find /etc/postgresql/ -name "pg_hba.conf" | head -n 1)

# Check if rule already exists to avoid duplicates
if ! grep -q "152.174.206.253" "$PG_HBA"; then
    echo "host    aurum_db        aurum_admin     152.174.206.253/32      md5" | sudo tee -a "$PG_HBA"
fi

echo "Restarting PostgreSQL service..."
sudo systemctl restart postgresql
sudo systemctl enable postgresql

echo "Creating database and user..."
# Create user if it doesn't exist
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='aurum_admin'" | grep -q 1 || sudo -u postgres psql -c "CREATE USER aurum_admin WITH PASSWORD 'AurumProyect1milion';"
# Create DB if it doesn't exist
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='aurum_db'" | grep -q 1 || sudo -u postgres psql -c "CREATE DATABASE aurum_db OWNER aurum_admin;"

echo "Installation and configuration complete."
sudo systemctl status postgresql --no-pager
