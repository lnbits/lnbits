from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .lnbits import LNbitsSettings


class ExtensionsSettings(LNbitsSettings):
    lnbits_admin_extensions: list[str] = Field(default=[])
    lnbits_user_default_extensions: list[str] = Field(default=[])
    lnbits_extensions_deactivate_all: bool = Field(default=False)
    lnbits_extensions_manifests: list[str] = Field(
        default=[
            "https://raw.githubusercontent.com/lnbits/lnbits-extensions/main/extensions.json"
        ]
    )


class ExtensionsInstallSettings(LNbitsSettings):
    lnbits_extensions_default_install: list[str] = Field(default=[])
    # required due to GitHUb rate-limit
    lnbits_ext_github_token: str = Field(default="")


class RedirectPath(BaseModel):
    ext_id: str
    from_path: str
    redirect_to_path: str
    header_filters: dict = {}

    def in_conflict(self, other: RedirectPath) -> bool:
        if self.ext_id == other.ext_id:
            return False
        return self.redirect_matches(
            other.from_path, list(other.header_filters.items())
        ) or other.redirect_matches(self.from_path, list(self.header_filters.items()))

    def find_in_conflict(self, others: list[RedirectPath]) -> Optional[RedirectPath]:
        for other in others:
            if self.in_conflict(other):
                return other
        return None

    def new_path_from(self, req_path: str) -> str:
        from_path = self.from_path.split("/")
        redirect_to = self.redirect_to_path.split("/")
        req_tail_path = req_path.split("/")[len(from_path) :]

        elements = [e for e in ([self.ext_id, *redirect_to, *req_tail_path]) if e != ""]

        return "/" + "/".join(elements)

    def redirect_matches(self, path: str, req_headers: list[tuple[str, str]]) -> bool:
        return self._has_common_path(path) and self._has_headers(req_headers)

    def _has_common_path(self, req_path: str) -> bool:
        if len(self.from_path) > len(req_path):
            return False

        redirect_path_elements = self.from_path.split("/")
        req_path_elements = req_path.split("/")

        sub_path = req_path_elements[: len(redirect_path_elements)]
        return self.from_path == "/".join(sub_path)

    def _has_headers(self, req_headers: list[tuple[str, str]]) -> bool:
        for h in self.header_filters:
            if not self._has_header(req_headers, (str(h), str(self.header_filters[h]))):
                return False
        return True

    def _has_header(
        self, req_headers: list[tuple[str, str]], header: tuple[str, str]
    ) -> bool:
        for h in req_headers:
            if h[0].lower() == header[0].lower() and h[1].lower() == header[1].lower():
                return True
        return False


class InstalledExtensionsSettings(LNbitsSettings):
    # installed extensions that have been deactivated
    lnbits_deactivated_extensions: set[str] = Field(default=[])
    # upgraded extensions that require API redirects
    lnbits_upgraded_extensions: dict[str, str] = Field(default={})
    # list of redirects that extensions want to perform
    lnbits_extensions_redirects: list[RedirectPath] = Field(default=[])

    # list of all extension ids
    lnbits_all_extensions_ids: set[Any] = Field(default=[])

    def find_extension_redirect(
        self, path: str, req_headers: list[tuple[bytes, bytes]]
    ) -> Optional[RedirectPath]:
        headers = [(k.decode(), v.decode()) for k, v in req_headers]
        return next(
            (
                r
                for r in self.lnbits_extensions_redirects
                if r.redirect_matches(path, headers)
            ),
            None,
        )

    def activate_extension_paths(
        self,
        ext_id: str,
        upgrade_hash: Optional[str] = None,
        ext_redirects: Optional[list[dict]] = None,
    ):
        self.lnbits_deactivated_extensions.discard(ext_id)

        """
        Update the list of upgraded extensions. The middleware will perform
        redirects based on this
        """
        if upgrade_hash:
            self.lnbits_upgraded_extensions[ext_id] = upgrade_hash

        if ext_redirects:
            self._activate_extension_redirects(ext_id, ext_redirects)

        self.lnbits_all_extensions_ids.add(ext_id)

    def deactivate_extension_paths(self, ext_id: str):
        self.lnbits_deactivated_extensions.add(ext_id)
        self._remove_extension_redirects(ext_id)

    def extension_upgrade_hash(self, ext_id: str) -> str:
        return self.lnbits_upgraded_extensions.get(ext_id, "")

    def _activate_extension_redirects(self, ext_id: str, ext_redirects: list[dict]):
        ext_redirect_paths = [
            RedirectPath(**{"ext_id": ext_id, **er}) for er in ext_redirects
        ]
        existing_redirects = {
            r.ext_id
            for r in self.lnbits_extensions_redirects
            if r.find_in_conflict(ext_redirect_paths)
        }

        assert len(existing_redirects) == 0, (
            f"Cannot redirect for extension '{ext_id}'."
            f" Already mapped by {existing_redirects}."
        )

        self._remove_extension_redirects(ext_id)
        self.lnbits_extensions_redirects += ext_redirect_paths

    def _remove_extension_redirects(self, ext_id: str):
        self.lnbits_extensions_redirects = [
            er for er in self.lnbits_extensions_redirects if er.ext_id != ext_id
        ]
