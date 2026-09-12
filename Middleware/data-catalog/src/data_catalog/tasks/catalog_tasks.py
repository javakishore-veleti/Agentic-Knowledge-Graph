"""All task classes (ADR-010).

Every task is a stateless singleton: it reads what it needs from the Ctx and writes what
it produces back to the Ctx. Nothing is stored on `self` beyond immutable wiring, because
one instance serves every concurrent request.

Each task resolves its DAO through DAO_FACTORY by interface, so no task names an
implementation class.
"""

from __future__ import annotations

from ..cache.i_app_cache_service import IAppCacheService
from ..common.context import BaseCtx
from ..common.errors import NotFoundError, ValidationError
from ..common.object_factory import DAO_FACTORY, SERVICE_FACTORY
from ..common.paging import clamp_limit, decode_cursor, encode_cursor
from ..common.task import ITask
from ..dao.i_catalog_dao import (
    IAppEndpointDao, IDataInstanceDao, IDataInstanceExecDao, IDatasetDao, IDomainDao, IMioDao,
)
from ..dtos.base_dtos import PageDto
from ..dtos.cache_dtos import CacheStrategyName
from ..dtos.catalog_dtos import (
    GetMioLineageResp, ListAppEndpointsResp, ListDataInstanceExecsResp,
    ListDataInstancesResp, ListDatasetsResp, ListDomainsResp, ListMiosResp,
)

# ---------------------------------------------------------------- shared tasks


class ResolvePagingTask(ITask):
    """Clamp the limit and decode the cursor once, for every paged use case.

    A malformed cursor fails here rather than being treated as "start from the
    beginning", which would silently re-serve the whole table and look like success.
    """

    name = "resolve_paging"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.scratch["limit"] = clamp_limit(getattr(ctx.req, "limit", None))
        raw = getattr(ctx.req, "cursor", None)
        try:
            cursor = decode_cursor(raw)
        except ValueError as exc:
            raise ValidationError(str(exc), ctx.trace_id) from exc
        ctx.scratch["after"] = cursor["after"] if cursor else None


class CacheLookupTask(ITask):
    """Serve from cache when possible, and tell later tasks to stand down.

    Reading the cache is a task rather than a wrapper so that a cache hit appears in the
    task trail. A hit that leaves no trace makes a fast request indistinguishable from a
    broken one.
    """

    name = "cache_lookup"

    def __init__(self, cache_name: str) -> None:
        self._cache_name = cache_name

    def execute(self, ctx: BaseCtx) -> None:
        cache: IAppCacheService = SERVICE_FACTORY.get(IAppCacheService)
        key_parts = ctx.req.model_dump(mode="json")
        hit = cache.get(self._cache_name, ctx.tenant_id, key_parts)
        if hit is not None:
            ctx.scratch["cache_hit"] = True
            ctx.scratch["cached_value"] = hit


class CacheStoreTask(ITask):
    """Write the response to cache. Skipped when the response came from cache."""

    name = "cache_store"

    def __init__(self, cache_name: str, *, strategy: CacheStrategyName, category_from: str | None = None) -> None:
        self._cache_name = cache_name
        self._strategy = strategy
        self._category_from = category_from

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit") and ctx.resp is not None

    def execute(self, ctx: BaseCtx) -> None:
        cache: IAppCacheService = SERVICE_FACTORY.get(IAppCacheService)
        category = None
        if self._category_from:
            category = getattr(ctx.req, self._category_from, None)
        cache.put(
            self._cache_name,
            ctx.tenant_id,
            ctx.req.model_dump(mode="json"),
            ctx.require_resp().model_dump(mode="json"),
            strategy=self._strategy,
            category=str(category) if category else None,
        )


# ---------------------------------------------------------------- domains


class CountDomainsTask(ITask):
    name = "count_domains"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IDomainDao = DAO_FACTORY.get(IDomainDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)


class FetchDomainsTask(ITask):
    name = "fetch_domains"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IDomainDao = DAO_FACTORY.get(IDomainDao)
        ctx.scratch["items"] = dao.find(
            ctx.tenant_id, ctx.req, ctx.scratch["limit"], ctx.scratch["after"]
        )


class BuildDomainsRespTask(ITask):
    name = "build_domains_resp"

    def execute(self, ctx: BaseCtx) -> None:
        if ctx.scratch.get("cache_hit"):
            ctx.resp = ListDomainsResp.model_validate(ctx.scratch["cached_value"])
            return
        items = ctx.scratch["items"]
        limit = ctx.scratch["limit"]
        nxt = encode_cursor({"after": items[-1].code}) if len(items) == limit and items else None
        ctx.resp = ListDomainsResp(
            page=PageDto(total=ctx.scratch["total"], limit=limit, next_cursor=nxt),
            items=items,
        )


# ---------------------------------------------------------------- datasets


class CountDatasetsTask(ITask):
    name = "count_datasets"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IDatasetDao = DAO_FACTORY.get(IDatasetDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)


class FetchDatasetsTask(ITask):
    name = "fetch_datasets"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IDatasetDao = DAO_FACTORY.get(IDatasetDao)
        ctx.scratch["items"] = dao.find(
            ctx.tenant_id, ctx.req, ctx.scratch["limit"], ctx.scratch["after"]
        )


class BuildDatasetsRespTask(ITask):
    name = "build_datasets_resp"

    def execute(self, ctx: BaseCtx) -> None:
        if ctx.scratch.get("cache_hit"):
            ctx.resp = ListDatasetsResp.model_validate(ctx.scratch["cached_value"])
            return
        items = ctx.scratch["items"]
        limit = ctx.scratch["limit"]
        nxt = encode_cursor({"after": items[-1].code}) if len(items) == limit and items else None
        ctx.resp = ListDatasetsResp(
            page=PageDto(total=ctx.scratch["total"], limit=limit, next_cursor=nxt),
            items=items,
        )


# ---------------------------------------------------------------- mios


class CountMiosTask(ITask):
    name = "count_mios"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioDao = DAO_FACTORY.get(IMioDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)


class FetchMiosTask(ITask):
    name = "fetch_mios"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioDao = DAO_FACTORY.get(IMioDao)
        ctx.scratch["items"] = dao.find(
            ctx.tenant_id, ctx.req, ctx.scratch["limit"], ctx.scratch["after"]
        )


class BuildMiosRespTask(ITask):
    name = "build_mios_resp"

    def execute(self, ctx: BaseCtx) -> None:
        if ctx.scratch.get("cache_hit"):
            ctx.resp = ListMiosResp.model_validate(ctx.scratch["cached_value"])
            return
        items = ctx.scratch["items"]
        limit = ctx.scratch["limit"]
        nxt = encode_cursor({"after": items[-1].code}) if len(items) == limit and items else None
        ctx.resp = ListMiosResp(
            page=PageDto(total=ctx.scratch["total"], limit=limit, next_cursor=nxt),
            items=items,
        )


# ---------------------------------------------------------------- instances


class VerifyMioExistsTask(ITask):
    """Distinguish "no instances" from "no such MIO".

    Returning an empty list for a MIO that does not exist makes a typo look like a
    correctly empty result.
    """

    name = "verify_mio_exists"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioDao = DAO_FACTORY.get(IMioDao)
        if not dao.exists(ctx.tenant_id, ctx.req.mio_id):
            raise NotFoundError("mio", str(ctx.req.mio_id), ctx.trace_id)


class FetchDataInstancesTask(ITask):
    name = "fetch_data_instances"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IDataInstanceDao = DAO_FACTORY.get(IDataInstanceDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)
        ctx.scratch["items"] = dao.find(ctx.tenant_id, ctx.req, ctx.scratch["limit"])
        ctx.scratch["cdc_id"] = dao.cdc_instance_id(ctx.tenant_id, ctx.req.mio_id)


class BuildDataInstancesRespTask(ITask):
    name = "build_data_instances_resp"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.resp = ListDataInstancesResp(
            page=PageDto(total=ctx.scratch["total"], limit=ctx.scratch["limit"]),
            items=ctx.scratch["items"],
            cdc_instance_id=ctx.scratch["cdc_id"],
        )


# ---------------------------------------------------------------- execs


class FetchExecsTask(ITask):
    name = "fetch_execs"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IDataInstanceExecDao = DAO_FACTORY.get(IDataInstanceExecDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)
        ctx.scratch["items"] = dao.find(ctx.tenant_id, ctx.req, ctx.scratch["limit"])


class BuildExecsRespTask(ITask):
    name = "build_execs_resp"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.resp = ListDataInstanceExecsResp(
            page=PageDto(total=ctx.scratch["total"], limit=ctx.scratch["limit"]),
            items=ctx.scratch["items"],
        )


# ---------------------------------------------------------------- endpoints


class FetchAppEndpointsTask(ITask):
    name = "fetch_app_endpoints"

    def should_run(self, ctx: BaseCtx) -> bool:
        return not ctx.scratch.get("cache_hit")

    def execute(self, ctx: BaseCtx) -> None:
        dao: IAppEndpointDao = DAO_FACTORY.get(IAppEndpointDao)
        ctx.scratch["total"] = dao.count(ctx.tenant_id, ctx.req)
        ctx.scratch["items"] = dao.find(ctx.tenant_id, ctx.req, ctx.scratch["limit"])


class BuildAppEndpointsRespTask(ITask):
    name = "build_app_endpoints_resp"

    def execute(self, ctx: BaseCtx) -> None:
        if ctx.scratch.get("cache_hit"):
            ctx.resp = ListAppEndpointsResp.model_validate(ctx.scratch["cached_value"])
            return
        ctx.resp = ListAppEndpointsResp(
            page=PageDto(total=ctx.scratch["total"], limit=ctx.scratch["limit"]),
            items=ctx.scratch["items"],
        )


# ---------------------------------------------------------------- lineage


class FetchLineageTask(ITask):
    name = "fetch_lineage"

    def execute(self, ctx: BaseCtx) -> None:
        dao: IMioDao = DAO_FACTORY.get(IMioDao)
        ctx.scratch["parents"] = dao.lineage_parents(ctx.req.mio_id)
        ctx.scratch["children"] = dao.lineage_children(ctx.req.mio_id)


class BuildLineageRespTask(ITask):
    name = "build_lineage_resp"

    def execute(self, ctx: BaseCtx) -> None:
        ctx.resp = GetMioLineageResp(
            mio_id=ctx.req.mio_id,
            produced_from=ctx.scratch["parents"],
            generated=ctx.scratch["children"],
        )
