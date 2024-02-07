import typing

from jinja2 import BaseLoader, Environment, pass_context
from starlette.datastructures import QueryParams
from starlette.requests import Request
from starlette.templating import Jinja2Templates as SuperJinja2Templates


class Jinja2Templates(SuperJinja2Templates):
    def __init__(self, loader: BaseLoader) -> None:
        self.env = self.get_environment(loader)
        super().__init__(env=self.env)

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
