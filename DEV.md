For developers
==============

LNbits uses [Flask](http://flask.pocoo.org/).  
Feel free to contribute to the project.

Application dependencies
------------------------
The application uses [Pipenv][pipenv] to manage Python packages.
While in development, you will need to install all dependencies:

    $ pipenv shell
    $ pipenv install --dev

Running the server
------------------

    $ flask run

There is an environment variable called `FLASK_ENV` that has to be set to `development`
if you want to run Flask in debug mode with autoreload

Style guide
-----------
Tab size is 4 spaces. Maximum line length is 120. You should run `black` before commiting any change.

    $ black lnbits

[pipenv]: https://docs.pipenv.org/#install-pipenv-today
