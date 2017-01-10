# Cool Item-Cataloger
An item catalog application written with Flask and sqlite3.

It provides:
* User authentication with Google+ account
* User registration system
* Item lists are grouped into categories.
* JSON API for all catalogs, any catalog, or any item
* Any user:
  * can see all categories and items, and item details.
* Registered users:
  * can create, update, and delete their own categories as well as items.

## Requirements
* Python 2.7.11
* SQLite 3.9.2
* Flask 0.9
* SQLAlchemy 1.0.12
* Google+ Client Secrets(client_secrets.json)

## Usage
* Download (or clone) the Repository
* To create database:
```
  python database_setup.py
```
* To populate database with seed data:
```
  python db_seed.py
```
* Run the application:
```
  python application.py
```
* Navigate to http://localhost:5000
