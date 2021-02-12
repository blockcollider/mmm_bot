

In the root dir of the project:

```
# to generate example order pairs for the api server
poetry run python -m scripts.generate_orders

# to remove all rows in the taker_orders and maker_orders tables
poetry run python -m scripts.clear_db
```
