import json
from pathlib import Path
from unittest import mock

import pytest

from taipy.common import utils
from taipy.common.alias import PipelineId, TaskId
from taipy.config.config import Config
from taipy.data.in_memory import InMemoryDataNode
from taipy.data.manager import DataManager
from taipy.data.scope import Scope
from taipy.exceptions import NonExistingTask
from taipy.exceptions.pipeline import NonExistingPipeline
from taipy.job.job_manager import JobManager
from taipy.pipeline import Pipeline
from taipy.pipeline.manager import PipelineManager
from taipy.scenario import ScenarioManager
from taipy.scheduler.scheduler import Scheduler
from taipy.task import Task
from taipy.task.manager import TaskManager
from tests.taipy.utils.NotifyMock import NotifyMock


@pytest.fixture()
def airflow_config():
    Config.set_job_config(mode=Config.job_config().MODE_VALUE_AIRFLOW, hostname="http://localhost:8080")
    yield
    Config.set_job_config(mode=Config.job_config().DEFAULT_MODE)


def test_set_and_get_pipeline():
    pipeline_manager = PipelineManager()

    pipeline_id_1 = PipelineId("id1")
    pipeline_1 = Pipeline("name_1", {}, [], pipeline_id_1)

    pipeline_id_2 = PipelineId("id2")
    input_2 = InMemoryDataNode("foo", Scope.PIPELINE)
    output_2 = InMemoryDataNode("foo", Scope.PIPELINE)
    task_2 = Task("task", [input_2], print, [output_2], TaskId("task_id_2"))
    pipeline_2 = Pipeline("name_2", {}, [task_2], pipeline_id_2)

    pipeline_3_with_same_id = Pipeline("name_3", {}, [], pipeline_id_1)

    # No existing Pipeline
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.get(pipeline_id_1)
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.get(pipeline_1)
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.get(pipeline_id_2)
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.get(pipeline_2)

    # Save one pipeline. We expect to have only one pipeline stored
    pipeline_manager.set(pipeline_1)
    assert pipeline_manager.get(pipeline_id_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_id_1).config_name == pipeline_1.config_name
    assert len(pipeline_manager.get(pipeline_id_1).tasks) == 0
    assert pipeline_manager.get(pipeline_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_1).config_name == pipeline_1.config_name
    assert len(pipeline_manager.get(pipeline_1).tasks) == 0
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.get(pipeline_id_2)
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.get(pipeline_2)

    # Save a second pipeline. Now, we expect to have a total of two pipelines stored
    TaskManager.set(task_2)
    pipeline_manager.set(pipeline_2)
    assert pipeline_manager.get(pipeline_id_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_id_1).config_name == pipeline_1.config_name
    assert len(pipeline_manager.get(pipeline_id_1).tasks) == 0
    assert pipeline_manager.get(pipeline_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_1).config_name == pipeline_1.config_name
    assert len(pipeline_manager.get(pipeline_1).tasks) == 0
    assert pipeline_manager.get(pipeline_id_2).id == pipeline_2.id
    assert pipeline_manager.get(pipeline_id_2).config_name == pipeline_2.config_name
    assert len(pipeline_manager.get(pipeline_id_2).tasks) == 1
    assert pipeline_manager.get(pipeline_2).id == pipeline_2.id
    assert pipeline_manager.get(pipeline_2).config_name == pipeline_2.config_name
    assert len(pipeline_manager.get(pipeline_2).tasks) == 1
    assert TaskManager.get(task_2.id).id == task_2.id

    # We save the first pipeline again. We expect nothing to change
    pipeline_manager.set(pipeline_1)
    assert pipeline_manager.get(pipeline_id_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_id_1).config_name == pipeline_1.config_name
    assert len(pipeline_manager.get(pipeline_id_1).tasks) == 0
    assert pipeline_manager.get(pipeline_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_1).config_name == pipeline_1.config_name
    assert len(pipeline_manager.get(pipeline_1).tasks) == 0
    assert pipeline_manager.get(pipeline_id_2).id == pipeline_2.id
    assert pipeline_manager.get(pipeline_id_2).config_name == pipeline_2.config_name
    assert len(pipeline_manager.get(pipeline_id_2).tasks) == 1
    assert pipeline_manager.get(pipeline_2).id == pipeline_2.id
    assert pipeline_manager.get(pipeline_2).config_name == pipeline_2.config_name
    assert len(pipeline_manager.get(pipeline_2).tasks) == 1
    assert TaskManager.get(task_2.id).id == task_2.id

    # We save a third pipeline with same id as the first one.
    # We expect the first pipeline to be updated
    pipeline_manager.set(pipeline_3_with_same_id)
    assert pipeline_manager.get(pipeline_id_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_id_1).config_name == pipeline_3_with_same_id.config_name
    assert len(pipeline_manager.get(pipeline_id_1).tasks) == 0
    assert pipeline_manager.get(pipeline_1).id == pipeline_1.id
    assert pipeline_manager.get(pipeline_1).config_name == pipeline_3_with_same_id.config_name
    assert len(pipeline_manager.get(pipeline_1).tasks) == 0
    assert pipeline_manager.get(pipeline_id_2).id == pipeline_2.id
    assert pipeline_manager.get(pipeline_id_2).config_name == pipeline_2.config_name
    assert len(pipeline_manager.get(pipeline_id_2).tasks) == 1
    assert pipeline_manager.get(pipeline_2).id == pipeline_2.id
    assert pipeline_manager.get(pipeline_2).config_name == pipeline_2.config_name
    assert len(pipeline_manager.get(pipeline_2).tasks) == 1
    assert TaskManager.get(task_2.id).id == task_2.id


def test_submit():
    data_node_1 = InMemoryDataNode("foo", Scope.PIPELINE, "s1")
    data_node_2 = InMemoryDataNode("bar", Scope.PIPELINE, "s2")
    data_node_3 = InMemoryDataNode("baz", Scope.PIPELINE, "s3")
    data_node_4 = InMemoryDataNode("qux", Scope.PIPELINE, "s4")
    data_node_5 = InMemoryDataNode("quux", Scope.PIPELINE, "s5")
    data_node_6 = InMemoryDataNode("quuz", Scope.PIPELINE, "s6")
    data_node_7 = InMemoryDataNode("corge", Scope.PIPELINE, "s7")
    task_1 = Task(
        "grault",
        [data_node_1, data_node_2],
        print,
        [data_node_3, data_node_4],
        TaskId("t1"),
    )
    task_2 = Task("garply", [data_node_3], print, [data_node_5], TaskId("t2"))
    task_3 = Task("waldo", [data_node_5, data_node_4], print, [data_node_6], TaskId("t3"))
    task_4 = Task("fred", [data_node_4], print, [data_node_7], TaskId("t4"))
    pipeline = Pipeline("plugh", {}, [task_4, task_2, task_1, task_3], PipelineId("p1"))

    class MockScheduler(Scheduler):
        submit_calls = []

        def submit_task(self, task: Task, callbacks=None):
            self.submit_calls.append(task)
            return None

    class MockPipelineManager(PipelineManager):
        @property
        def scheduler(self):
            return MockScheduler()

    pipeline_manager = MockPipelineManager()

    # pipeline does not exists. We expect an exception to be raised
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.submit(pipeline.id)
    with pytest.raises(NonExistingPipeline):
        pipeline_manager.submit(pipeline)

    # pipeline does exist, but tasks does not exist. We expect an exception to be raised
    pipeline_manager.set(pipeline)
    with pytest.raises(NonExistingTask):
        pipeline_manager.submit(pipeline.id)
    with pytest.raises(NonExistingTask):
        pipeline_manager.submit(pipeline)

    # pipeline, and tasks does exist. We expect the tasks to be submitted
    # in a specific order
    TaskManager.set(task_1)
    TaskManager.set(task_2)
    TaskManager.set(task_3)
    TaskManager.set(task_4)

    pipeline_manager.submit(pipeline.id)
    calls_ids = [t.id for t in pipeline_manager.scheduler.submit_calls]
    tasks_ids = [task_1.id, task_2.id, task_4.id, task_3.id]
    assert calls_ids == tasks_ids

    pipeline_manager.submit(pipeline)
    calls_ids = [t.id for t in pipeline_manager.scheduler.submit_calls]
    tasks_ids = tasks_ids * 2
    assert set(calls_ids) == set(tasks_ids)


def mult_by_2(nb: int):
    return nb * 2


def mult_by_3(nb: int):
    return nb * 3


def test_get_or_create_data():
    # only create intermediate data node once
    pipeline_manager = PipelineManager()

    ds_config_1 = Config.add_data_node("foo", "in_memory", Scope.PIPELINE, default_data=1)
    ds_config_2 = Config.add_data_node("bar", "in_memory", Scope.PIPELINE, default_data=0)
    ds_config_6 = Config.add_data_node("baz", "in_memory", Scope.PIPELINE, default_data=0)

    task_config_mult_by_2 = Config.add_task("mult by 2", [ds_config_1], mult_by_2, ds_config_2)
    task_config_mult_by_3 = Config.add_task("mult by 3", [ds_config_2], mult_by_3, ds_config_6)
    pipeline_config = Config.add_pipeline("by 6", [task_config_mult_by_2, task_config_mult_by_3])
    # ds_1 ---> mult by 2 ---> ds_2 ---> mult by 3 ---> ds_6

    assert len(DataManager.get_all()) == 0
    assert len(TaskManager.get_all()) == 0

    pipeline = pipeline_manager.get_or_create(pipeline_config)

    assert len(DataManager.get_all()) == 3
    assert len(TaskManager.get_all()) == 2
    assert len(pipeline.get_sorted_tasks()) == 2
    assert pipeline.foo.read() == 1
    assert pipeline.bar.read() == 0
    assert pipeline.baz.read() == 0
    assert pipeline.get_sorted_tasks()[0][0].config_name == task_config_mult_by_2.name
    assert pipeline.get_sorted_tasks()[1][0].config_name == task_config_mult_by_3.name

    pipeline_manager.submit(pipeline.id)
    assert pipeline.foo.read() == 1
    assert pipeline.bar.read() == 2
    assert pipeline.baz.read() == 6

    pipeline.foo.write("new data value")
    assert pipeline.foo.read() == "new data value"
    assert pipeline.bar.read() == 2
    assert pipeline.baz.read() == 6

    pipeline.bar.write(7)
    assert pipeline.foo.read() == "new data value"
    assert pipeline.bar.read() == 7
    assert pipeline.baz.read() == 6

    with pytest.raises(AttributeError):
        pipeline.WRONG.write(7)


def test_pipeline_notification_subscribe_unsubscribe(mocker):
    pipeline_manager = PipelineManager()

    pipeline_config = Config.add_pipeline(
        "by 6",
        [
            Config.add_task(
                "mult by 2",
                [Config.add_data_node("foo", "in_memory", Scope.PIPELINE, default_data=1)],
                mult_by_2,
                Config.add_data_node("bar", "in_memory", Scope.PIPELINE, default_data=0),
            )
        ],
    )

    pipeline = pipeline_manager.get_or_create(pipeline_config)

    notify_1 = NotifyMock(pipeline)
    notify_1.__name__ = "notify_1"
    notify_1.__module__ = "notify_1"
    notify_2 = NotifyMock(pipeline)
    notify_2.__name__ = "notify_2"
    notify_2.__module__ = "notify_2"
    # Mocking this because NotifyMock is a class that does not loads correctly when getting the pipeline
    # from the storage.
    mocker.patch.object(utils, "load_fct", side_effect=[notify_1, notify_2])

    # test subscription
    callback = mock.MagicMock()
    callback.__name__ = "callback"
    callback.__module__ = "callback"
    pipeline_manager.submit(pipeline.id, [callback])
    callback.assert_called()

    # test pipeline subscribe notification
    pipeline_manager.subscribe(notify_1, pipeline)
    pipeline_manager.submit(pipeline.id)

    notify_1.assert_called_3_times()

    notify_1.reset()

    # test pipeline unsubscribe notification
    # test subscribe notification only on new job
    pipeline_manager.unsubscribe(notify_1, pipeline)
    pipeline_manager.subscribe(notify_2, pipeline)
    pipeline_manager.submit(pipeline.id)

    notify_1.assert_not_called()
    notify_2.assert_called_3_times()

    with pytest.raises(KeyError):
        pipeline_manager.unsubscribe(notify_1, pipeline)
        pipeline_manager.unsubscribe(notify_2, pipeline)


def test_pipeline_notification_subscribe_all():
    pipeline_manager = PipelineManager()
    pipeline_config = Config.add_pipeline(
        "by 6",
        [
            Config.add_task(
                "mult by 2",
                [Config.add_data_node("foo", "in_memory", Scope.PIPELINE, default_data=1)],
                mult_by_2,
                Config.add_data_node("bar", "in_memory", Scope.PIPELINE, default_data=0),
            )
        ],
    )

    pipeline = PipelineManager().get_or_create(pipeline_config)
    pipeline_config.name = "other pipeline"

    other_pipeline = PipelineManager().get_or_create(pipeline_config)

    notify_1 = NotifyMock(pipeline)

    pipeline_manager.subscribe(notify_1)

    assert len(pipeline_manager.get(pipeline.id).subscribers) == 1
    assert len(pipeline_manager.get(other_pipeline.id).subscribers) == 1


def test_get_all_by_config_name():
    pm = PipelineManager()
    input_configs = [Config.add_data_node("my_input", "in_memory")]
    task_config_1 = Config.add_task("task_config_1", input_configs, print, [])
    assert len(pm._get_all_by_config_name("NOT_EXISTING_CONFIG_NAME")) == 0
    pipeline_config_1 = Config.add_pipeline("foo", [task_config_1])
    assert len(pm._get_all_by_config_name("foo")) == 0

    pm.get_or_create(pipeline_config_1)
    assert len(pm._get_all_by_config_name("foo")) == 1

    pipeline_config_2 = Config.add_pipeline("baz", [task_config_1])
    pm.get_or_create(pipeline_config_2)
    assert len(pm._get_all_by_config_name("foo")) == 1
    assert len(pm._get_all_by_config_name("baz")) == 1

    pm.get_or_create(pipeline_config_2, "other_scenario")
    assert len(pm._get_all_by_config_name("foo")) == 1
    assert len(pm._get_all_by_config_name("baz")) == 2


def test_do_not_recreate_existing_pipeline_except_same_config():
    pm = PipelineManager()
    ds_input_config_scope_scenario = Config.add_data_node("my_input", "in_memory", scope=Scope.SCENARIO)
    ds_output_config_scope_scenario = Config.add_data_node("my_output", "in_memory", scope=Scope.SCENARIO)
    task_config = Config.add_task("task_config", ds_input_config_scope_scenario, print, ds_output_config_scope_scenario)
    pipeline_config = Config.add_pipeline("pipeline_config_1", [task_config])

    # Scope is scenario
    pipeline_1 = pm.get_or_create(pipeline_config)
    assert len(pm.get_all()) == 1
    pipeline_2 = pm.get_or_create(pipeline_config)
    assert len(pm.get_all()) == 1
    assert pipeline_1.id == pipeline_2.id
    pipeline_3 = pm.get_or_create(pipeline_config, "a_scenario")  # Create even if the config is the same
    assert len(pm.get_all()) == 2
    assert pipeline_1.id == pipeline_2.id
    assert pipeline_3.id != pipeline_1.id
    assert pipeline_3.id != pipeline_2.id
    pipeline_4 = pm.get_or_create(pipeline_config, "a_scenario")  # Do not create because existed pipeline
    assert len(pm.get_all()) == 2
    assert pipeline_3.id == pipeline_4.id

    ds_input_config_scope_scenario_2 = Config.add_data_node("my_input_2", "in_memory", scope=Scope.SCENARIO)
    ds_output_config_scope_global_2 = Config.add_data_node("my_output_2", "in_memory", scope=Scope.GLOBAL)
    task_config_2 = Config.add_task(
        "task_config_2", ds_input_config_scope_scenario_2, print, ds_output_config_scope_global_2
    )
    pipeline_config_2 = Config.add_pipeline("pipeline_config_2", [task_config_2])

    # Scope is scenario and global
    pipeline_5 = pm.get_or_create(pipeline_config_2)
    assert len(pm.get_all()) == 3
    pipeline_6 = pm.get_or_create(pipeline_config_2)
    assert len(pm.get_all()) == 3
    assert pipeline_5.id == pipeline_6.id
    pipeline_7 = pm.get_or_create(pipeline_config_2, "another_scenario")
    assert len(pm.get_all()) == 4
    assert pipeline_7.id != pipeline_6.id
    assert pipeline_7.id != pipeline_5.id
    pipeline_8 = pm.get_or_create(pipeline_config_2, "another_scenario")
    assert len(pm.get_all()) == 4
    assert pipeline_7.id == pipeline_8.id

    ds_input_config_scope_global_3 = Config.add_data_node("my_input_3", "in_memory", scope=Scope.GLOBAL)
    ds_output_config_scope_global_3 = Config.add_data_node("my_output_3", "in_memory", scope=Scope.GLOBAL)
    task_config_3 = Config.add_task(
        "task_config_3", ds_input_config_scope_global_3, print, ds_output_config_scope_global_3
    )
    pipeline_config_3 = Config.add_pipeline("pipeline_config_3", [task_config_3])

    # Scope is global
    pipeline_9 = pm.get_or_create(pipeline_config_3)
    assert len(pm.get_all()) == 5
    pipeline_10 = pm.get_or_create(pipeline_config_3)
    assert len(pm.get_all()) == 5
    assert pipeline_9.id == pipeline_10.id
    pipeline_11 = pm.get_or_create(pipeline_config_3, "another_new_scenario")  # Do not create because scope is global
    assert len(pm.get_all()) == 5
    assert pipeline_11.id == pipeline_10.id
    assert pipeline_11.id == pipeline_9.id

    ds_input_config_scope_pipeline_4 = Config.add_data_node("my_input_4", "in_memory", scope=Scope.PIPELINE)
    ds_output_config_scope_global_4 = Config.add_data_node("my_output_4", "in_memory", scope=Scope.GLOBAL)
    task_config_4 = Config.add_task(
        "task_config_4", ds_input_config_scope_pipeline_4, print, ds_output_config_scope_global_4
    )
    pipeline_config_4 = Config.add_pipeline("pipeline_config_4", [task_config_4])

    # Scope is global and pipeline
    pipeline_12 = pm.get_or_create(pipeline_config_4)
    assert len(pm.get_all()) == 6
    pipeline_13 = pm.get_or_create(pipeline_config_4)  # Create a new pipeline because new pipeline ID
    assert len(pm.get_all()) == 7
    assert pipeline_12.id != pipeline_13.id
    pipeline_14 = pm.get_or_create(pipeline_config_4, "another_new_scenario_2")
    assert len(pm.get_all()) == 8
    assert pipeline_14.id != pipeline_12.id
    assert pipeline_14.id != pipeline_13.id
    pipeline_15 = pm.get_or_create(
        pipeline_config_4, "another_new_scenario_2"
    )  # Don't create because scope is pipeline
    assert len(pm.get_all()) == 9
    assert pipeline_15.id != pipeline_14.id
    assert pipeline_15.id != pipeline_13.id
    assert pipeline_15.id != pipeline_12.id

    ds_input_config_scope_pipeline_5 = Config.add_data_node("my_input_5", "in_memory", scope=Scope.PIPELINE)
    ds_output_config_scope_scenario_5 = Config.add_data_node("my_output_5", "in_memory", scope=Scope.SCENARIO)
    task_config_5 = Config.add_task(
        "task_config_5", ds_input_config_scope_pipeline_5, print, ds_output_config_scope_scenario_5
    )
    pipeline_config_5 = Config.add_pipeline("pipeline_config_5", [task_config_5])

    # Scope is scenario and pipeline
    pipeline_16 = pm.get_or_create(pipeline_config_5)
    assert len(pm.get_all()) == 10
    pipeline_17 = pm.get_or_create(pipeline_config_5)
    assert len(pm.get_all()) == 11
    assert pipeline_16.id != pipeline_17.id
    pipeline_18 = pm.get_or_create(pipeline_config_5, "random_scenario")  # Create because scope is pipeline
    assert len(pm.get_all()) == 12
    assert pipeline_18.id != pipeline_17.id
    assert pipeline_18.id != pipeline_16.id

    # create a second pipeline from the same config
    ds_input_config_scope_pipeline_6 = Config.add_data_node("my_input_6", "in_memory")
    ds_output_config_scope_pipeline_6 = Config.add_data_node("my_output_6", "in_memory")
    task_config_6 = Config.add_task(
        "task_config_6", ds_input_config_scope_pipeline_6, print, ds_output_config_scope_pipeline_6
    )
    pipeline_config_6 = Config.add_pipeline("pipeline_config_6", [task_config_6])

    pipeline_19 = pm.get_or_create(pipeline_config_6)
    assert len(pm.get_all()) == 13
    pipeline_20 = pm.get_or_create(pipeline_config_6)
    assert len(pm.get_all()) == 14
    assert pipeline_19.id != pipeline_20.id


def test_hard_delete():
    scenario_manager = ScenarioManager()
    pipeline_manager = scenario_manager.pipeline_manager

    #  test hard delete with pipeline at pipeline level
    ds_input_config_1 = Config.add_data_node("my_input_1", "in_memory", scope=Scope.PIPELINE, default_data="testing")
    ds_output_config_1 = Config.add_data_node("my_output_1", "in_memory", default_data="works !")
    task_config_1 = Config.add_task("task_config_1", ds_input_config_1, print, ds_output_config_1)
    pipeline_config_1 = Config.add_pipeline("pipeline_config_1", [task_config_1])
    pipeline_1 = pipeline_manager.get_or_create(pipeline_config_1)
    pipeline_manager.submit(pipeline_1.id)

    assert len(pipeline_manager.get_all()) == 1
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1
    pipeline_manager.hard_delete(pipeline_1.id)
    assert len(pipeline_manager.get_all()) == 0
    assert len(TaskManager.get_all()) == 0
    assert len(DataManager.get_all()) == 0
    assert len(JobManager.get_all()) == 0

    #  test hard delete with pipeline at scenario level
    ds_input_config_2 = Config.add_data_node("my_input_2", "in_memory", scope=Scope.SCENARIO, default_data="testing")
    ds_output_config_2 = Config.add_data_node("my_output_2", "in_memory", scope=Scope.SCENARIO)
    task_config_2 = Config.add_task("task_config_2", ds_input_config_2, print, ds_output_config_2)
    pipeline_config_2 = Config.add_pipeline("pipeline_config_2", [task_config_2])
    pipeline_2 = pipeline_manager.get_or_create(pipeline_config_2)
    pipeline_manager.submit(pipeline_2.id)

    assert len(pipeline_manager.get_all()) == 1
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1
    pipeline_manager.hard_delete(pipeline_2.id)
    assert len(pipeline_manager.get_all()) == 0
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1

    scenario_manager.delete_all()
    pipeline_manager.delete_all()
    DataManager.delete_all()
    TaskManager.delete_all()
    JobManager.delete_all()

    #  test hard delete with pipeline at business level
    ds_input_config_3 = Config.add_data_node(
        "my_input_3", "in_memory", scope=Scope.BUSINESS_CYCLE, default_data="testing"
    )
    ds_output_config_3 = Config.add_data_node("my_output_3", "in_memory", scope=Scope.BUSINESS_CYCLE)
    task_config_3 = Config.add_task("task_config_3", ds_input_config_3, print, ds_output_config_3)
    pipeline_config_3 = Config.add_pipeline("pipeline_config_3", [task_config_3])
    pipeline_3 = pipeline_manager.get_or_create(pipeline_config_3)
    pipeline_manager.submit(pipeline_3.id)

    assert len(pipeline_manager.get_all()) == 1
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1
    pipeline_manager.hard_delete(pipeline_3.id)
    assert len(pipeline_manager.get_all()) == 0
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1

    scenario_manager.delete_all()
    pipeline_manager.delete_all()
    DataManager.delete_all()
    TaskManager.delete_all()
    JobManager.delete_all()

    #  test hard delete with pipeline at global level
    ds_input_config_4 = Config.add_data_node("my_input_4", "in_memory", scope=Scope.GLOBAL, default_data="testing")
    ds_output_config_4 = Config.add_data_node("my_output_4", "in_memory", scope=Scope.GLOBAL)
    task_config_4 = Config.add_task("task_config_4", ds_input_config_4, print, ds_output_config_4)
    pipeline_config_4 = Config.add_pipeline("pipeline_config_4", [task_config_4])
    pipeline_4 = pipeline_manager.get_or_create(pipeline_config_4)
    pipeline_manager.submit(pipeline_4.id)

    assert len(pipeline_manager.get_all()) == 1
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1
    pipeline_manager.hard_delete(pipeline_4.id)
    assert len(pipeline_manager.get_all()) == 0
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1

    scenario_manager.delete_all()
    pipeline_manager.delete_all()
    DataManager.delete_all()
    TaskManager.delete_all()
    JobManager.delete_all()

    ds_input_config_5 = Config.add_data_node("my_input_5", "in_memory", scope=Scope.PIPELINE, default_data="testing")
    ds_output_config_5 = Config.add_data_node("my_output_5", "in_memory", scope=Scope.GLOBAL)
    task_config_5 = Config.add_task("task_config_5", ds_input_config_5, print, ds_output_config_5)
    pipeline_config_5 = Config.add_pipeline("pipeline_config_5", [task_config_5])
    pipeline_5 = pipeline_manager.get_or_create(pipeline_config_5)
    pipeline_manager.submit(pipeline_5.id)

    assert len(pipeline_manager.get_all()) == 1
    assert len(TaskManager.get_all()) == 1
    assert len(DataManager.get_all()) == 2
    assert len(JobManager.get_all()) == 1
    pipeline_manager.hard_delete(pipeline_5.id)
    assert len(pipeline_manager.get_all()) == 0
    assert len(TaskManager.get_all()) == 0
    assert len(DataManager.get_all()) == 1
    assert len(JobManager.get_all()) == 0


# TODO REACTIVATE
@pytest.mark.skip(reason="TEMPORARY DEACTIVATED until TaskManager and others become real singleton")
def test_generate_json():
    class Response:
        status_code = 200

    TaskManager._scheduler = None
    Config.set_job_config(mode=Config.job_config().MODE_VALUE_AIRFLOW, hostname="http://localhost:8080")

    ds_input_config = Config.add_data_node(name="test_data_node_input")
    ds_output_config = Config.add_data_node(name="test_data_node_output")
    task_config = Config.add_task("task_config", ds_input_config, print, ds_output_config)
    pipeline_config = Config.add_pipeline("pipeline_config", [task_config])
    pm = PipelineManager()
    pipeline = pm.get_or_create(pipeline_config)
    pipeline.task_config.test_data_node_input.write("foo")
    DataManager.set(pipeline.task_config.test_data_node_input)
    with mock.patch("taipy.scheduler.airflow.airflow_scheduler.requests.get") as get, mock.patch(
        "taipy.scheduler.airflow.airflow_scheduler.requests.patch"
    ) as patch, mock.patch("taipy.scheduler.airflow.airflow_scheduler.requests.post") as post:
        get.return_value = Response()
        pm.scheduler.get_credentials = mock.MagicMock()
        pm.submit(pipeline.id)

        get.assert_called_once()
        post.assert_called_once()
        patch.assert_called_once()

    dag_as_json = Path(Config.job_config().airflow_dags_folder).resolve() / "taipy" / f"{pipeline.id}.json"
    data = json.loads(dag_as_json.read_text())

    assert data["path"] == pm.scheduler.generate_airflow_path()
    assert data["dag_id"] == pipeline.id
    assert data["storage_folder"] == pm.scheduler.generate_storage_folder_path()
    assert data["tasks"] == [task.id for task in pipeline.tasks.values()]

    pm.scheduler.stop()
