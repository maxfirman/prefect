import datetime
from tests.fixtures.database import session
from uuid import uuid4
import uuid

import pendulum
import pytest
import sqlalchemy as sa
from sqlalchemy.sql.functions import mode

from prefect.orion import models, schemas
from prefect.orion.models import deployments, orm
from prefect.orion.schemas.states import StateType
from prefect.orion.schemas.data import DataDocument


class TestCreateDeployment:
    async def test_create_deployment_succeeds(self, session, flow, flow_function):

        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow.id,
                tags=["foo", "bar"],
            ),
        )
        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.flow_data == flow_data
        assert deployment.tags == ["foo", "bar"]

    async def test_create_deployment_updates_existing_deployment(
        self, session, flow, flow_function
    ):

        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow.id,
            ),
        )

        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.flow_data == flow_data
        assert deployment.tags == []

        schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )

        flow_data = DataDocument.encode("json", "test-override")
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                flow_data=flow_data,
                schedule=schedule,
                is_schedule_active=False,
                tags=["foo", "bar"],
            ),
        )
        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.flow_data == flow_data
        assert not deployment.is_schedule_active
        assert deployment.schedule == schedule
        assert deployment.tags == ["foo", "bar"]

    async def test_create_deployment_with_schedule(self, session, flow, flow_function):
        schedule = schemas.schedules.IntervalSchedule(
            interval=datetime.timedelta(days=1)
        )
        flow_data = DataDocument.encode("cloudpickle", flow_function)

        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_id=flow.id,
                flow_data=flow_data,
                schedule=schedule,
            ),
        )
        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id
        assert deployment.flow_data == flow_data
        assert deployment.schedule == schedule


class TestReadDeployment:
    async def test_read_deployment(self, session, flow, flow_function):
        # create a deployment to read

        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow.id,
            ),
        )
        assert deployment.name == "My Deployment"

        read_deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        assert deployment.id == read_deployment.id
        assert deployment.name == read_deployment.name

    async def test_read_deployment_returns_none_if_does_not_exist(self, session):
        result = await models.deployments.read_deployment(
            session=session, deployment_id=str(uuid4())
        )
        assert result is None

    async def test_read_deployment_by_name(self, session, flow, flow_function):
        # create a deployment to read
        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow.id,
            ),
        )
        assert deployment.name == "My Deployment"

        read_deployment = await models.deployments.read_deployment_by_name(
            session=session,
            name=deployment.name,
            flow_name=flow.name,
        )
        assert deployment.id == read_deployment.id
        assert deployment.name == read_deployment.name

    async def test_read_deployment_by_name_does_not_return_deployments_from_other_flows(
        self, session, flow_function
    ):
        flow_1, flow_2 = [
            await models.flows.create_flow(
                session=session, flow=schemas.core.Flow(name=f"my-flow-{i}")
            )
            for i in range(2)
        ]

        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment_1 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow_1.id,
            ),
        )
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow_2.id,
            ),
        )

        read_deployment = await models.deployments.read_deployment_by_name(
            session=session,
            name=deployment_1.name,
            flow_name=flow_1.name,
        )
        assert read_deployment.id == deployment_1.id

    async def test_read_deployment_by_name_returns_none_if_does_not_exist(
        self, session
    ):
        result = await models.deployments.read_deployment_by_name(
            session=session,
            name=str(uuid4()),
            flow_name=str(uuid4()),
        )
        assert result is None


class TestReadDeployments:
    @pytest.fixture
    async def deployments(self, session, flow, flow_function):
        flow_data = DataDocument.encode("cloudpickle", flow_function)

        deployment_1 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment-1",
                flow_data=flow_data,
                flow_id=flow.id,
            ),
        )
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment-2",
                flow_data=flow_data,
                flow_id=flow.id,
            ),
        )
        await session.commit()
        return [deployment_1, deployment_2]

    async def test_read_deployments(self, deployments, session):
        read_deployments = await models.deployments.read_deployments(session=session)
        assert len(read_deployments) == len(deployments)

    async def test_read_deployments_applies_limit(self, deployments, session):
        read_deployments = await models.deployments.read_deployments(
            session=session, limit=1
        )
        assert len(read_deployments) == 1

    async def test_read_deployments_applies_offset(self, deployments, session):
        read_deployments = await models.deployments.read_deployments(
            session=session, offset=1
        )

    async def test_read_deployments_returns_empty_list(self, session):
        read_deployments = await models.deployments.read_deployments(session=session)
        assert len(read_deployments) == 0


class TestDeleteDeployment:
    async def test_delete_deployment(self, session, flow, flow_function):
        # create a deployment to delete

        flow_data = DataDocument.encode("cloudpickle", flow_function)
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=flow_data,
                flow_id=flow.id,
            ),
        )
        assert deployment.name == "My Deployment"

        assert await models.deployments.delete_deployment(
            session=session, deployment_id=deployment.id
        )

        # make sure the deployment is deleted
        result = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        assert result is None

    async def test_delete_deployment_returns_false_if_does_not_exist(self, session):
        result = await models.deployments.delete_deployment(
            session=session, deployment_id=str(uuid4())
        )
        assert result is False


class TestScheduledRuns:
    async def test_schedule_runs_inserts_in_db(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id
        )
        assert len(scheduled_runs) == 100
        query_result = await session.execute(
            sa.select(orm.FlowRun).where(
                orm.FlowRun.state.has(orm.FlowRunState.type == StateType.SCHEDULED)
            )
        )

        db_scheduled_runs = query_result.scalars().all()
        assert {r.id for r in db_scheduled_runs} == {r.id for r in scheduled_runs}

        expected_times = {
            pendulum.now("UTC").start_of("day").add(days=i + 1) for i in range(100)
        }
        assert {
            r.state.state_details.scheduled_time for r in db_scheduled_runs
        } == expected_times

    async def test_schedule_runs_is_idempotent(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id
        )
        assert len(scheduled_runs) == 100

        second_scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id
        )

        assert len(second_scheduled_runs) == 0

        # only 100 runs were inserted
        query_result = await session.execute(
            sa.select(orm.FlowRun).where(
                orm.FlowRun.flow_id == flow.id,
                orm.FlowRun.state.has(orm.FlowRunState.type == StateType.SCHEDULED),
            )
        )

        db_scheduled_runs = query_result.scalars().all()
        assert len(db_scheduled_runs) == 100

    async def test_schedule_n_runs(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=3
        )
        assert len(scheduled_runs) == 3

    async def test_schedule_does_not_error_if_theres_no_schedule(
        self, flow, flow_function, session
    ):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                flow_id=flow.id,
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=3
        )
        assert scheduled_runs == []

    @pytest.mark.parametrize("tags", [[], ["foo"]])
    async def test_schedule_runs_applies_tags(self, tags, flow, flow_function, session):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My Deployment",
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
                flow_id=flow.id,
                tags=tags,
            ),
        )
        scheduled_runs = await models.deployments.schedule_runs(
            session, deployment_id=deployment.id, max_runs=2
        )
        assert len(scheduled_runs) == 2
        for run in scheduled_runs:
            assert run.tags == ["auto-scheduled"] + tags

    async def test_schedule_runs_with_end_time(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            end_time=pendulum.now("UTC").add(days=17),
        )
        assert len(scheduled_runs) == 17

    async def test_schedule_runs_with_start_time(self, flow, deployment, session):
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            start_time=pendulum.now("UTC").add(days=100),
            end_time=pendulum.now("UTC").add(days=150),
        )
        assert len(scheduled_runs) == 50

        expected_times = {
            pendulum.now("UTC").start_of("day").add(days=i + 1) for i in range(100, 150)
        }
        assert {
            r.state.state_details.scheduled_time for r in scheduled_runs
        } == expected_times

    async def test_schedule_runs_with_times_and_max_number(
        self, flow, deployment, session
    ):
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            start_time=pendulum.now("UTC").add(days=100),
            end_time=pendulum.now("UTC").add(days=150),
            max_runs=3,
        )
        assert len(scheduled_runs) == 3

        expected_times = {
            pendulum.now("UTC").start_of("day").add(days=i + 1) for i in range(100, 103)
        }
        assert {
            r.state.state_details.scheduled_time for r in scheduled_runs
        } == expected_times

    async def test_backfill(self, flow, deployment, session):
        # backfills are just schedules for past dates...
        scheduled_runs = await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
            start_time=pendulum.now("UTC").subtract(days=1000),
            end_time=pendulum.now("UTC").subtract(days=950),
        )
        assert len(scheduled_runs) == 50

        expected_times = {
            pendulum.now("UTC").start_of("day").subtract(days=i)
            for i in range(950, 1000)
        }
        assert {
            r.state.state_details.scheduled_time for r in scheduled_runs
        } == expected_times

    async def test_run_details_are_applied_to_scheduled_runs(self, deployment, session):
        await models.deployments.schedule_runs(
            session,
            deployment_id=deployment.id,
        )

        all_runs = await models.flow_runs.read_flow_runs(session)
        assert all_runs
        for r in all_runs:
            assert r.state_type == schemas.states.StateType.SCHEDULED
            assert r.expected_start_time is not None
            assert r.expected_start_time == r.next_scheduled_start_time

    async def test_scheduling_multiple_batches_correctly_updates_runs(
        self, session, deployment, flow_function, flow
    ):
        # ensures that updating flow run states works correctly and doesnt set
        # any to None inadvertently
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="My second deployment",
                flow_data=DataDocument.encode("cloudpickle", flow_function),
                flow_id=flow.id,
                schedule=schemas.schedules.IntervalSchedule(
                    interval=datetime.timedelta(days=1)
                ),
            ),
        )

        # delete all runs
        await session.execute(sa.delete(models.orm.FlowRun))

        # schedule runs
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment.id
        )

        result = await session.execute(
            sa.select(sa.func.count(models.orm.FlowRun.id)).where(
                models.orm.FlowRun.state_id.is_(None)
            )
        )
        # no runs with missing states
        assert result.scalar() == 0

        # schedule more runs from a different deployment
        await models.deployments.schedule_runs(
            session=session, deployment_id=deployment_2.id
        )

        result = await session.execute(
            sa.select(sa.func.count(models.orm.FlowRun.id)).where(
                models.orm.FlowRun.state_id.is_(None)
            )
        )
        # no runs with missing states
        assert result.scalar() == 0
