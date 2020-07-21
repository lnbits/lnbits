pip install pipenv

if [ "${FLASK_ENV}" = "development" ]; then
  pipenv install --deploy --system --dev
else
  pipenv install --deploy --system
fi
