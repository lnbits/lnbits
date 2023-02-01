import typing

from starlette import templating
from starlette.datastructures import QueryParams
from starlette.requests import Request

from jinja2 import BaseLoader, Environment, pass_context


class Jinja2Templates(templating.Jinja2Templates):
    def __init__(self, loader: BaseLoader) -> None:
        self.env = self.get_environment(loader)

    def get_environment(self, loader: BaseLoader) -> Environment:
        @pass_context
        def url_for(context: dict, name: str, **path_params: typing.Any) -> str:
            request: Request = context["request"]
            return request.app.url_path_for(name, **path_params)

        def url_params_update(init: QueryParams, **new: typing.Any) -> QueryParams:
            values = dict(init)
            values.update(new)
            return QueryParams(**values)

        env = Environment(loader=loader, autoescape=True)
        env.globals["url_for"] = url_for
        env.globals["url_params_update"] = url_params_update
        return env
