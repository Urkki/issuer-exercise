# issuer-exercise
A demonstration of issuer in banking process. This project is developed with Python 3.7.0 32-bit version.
To load money for account, go to project root directory and use command: `python manage.py load_money <account_name> <amount> <currency>`.
To run unit tests, use `python manage.py test` command.


This project uses following Python packages:

* Django
* py-moneyed 
* pytz
* djangorestframework

### API endpoints

| URL | METHOD | Description |
| ------ | ------ | ------ |
|/api/authorization | POST | Used for handling authorization messages. |
|/api/presentment | POST | Used for handling presentment messages. |
