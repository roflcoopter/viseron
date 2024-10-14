"""Viseron init file."""
from __future__ import annotations

import concurrent.futures
import json
import logging
import multiprocessing.process
import os
import sys
import threading
import time
import tracemalloc
from collections.abc import Callable
from functools import partial
from timeit import default_timer as timer
from typing import TYPE_CHECKING, Any, Literal, overload

import voluptuous as vol
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import SchedulerNotRunningError
from sqlalchemy import insert

from viseron.components import (
    CriticalComponentsConfigStore,
    activate_safe_mode,
    get_component,
    setup_component,
    setup_components,
    setup_domains,
)
from viseron.components.data_stream import (
    COMPONENT as DATA_STREAM_COMPONENT,
    DataStream,
)
from viseron.components.nvr.const import (
    COMPONENT as NVR_COMPONENT,
    DOMAIN as NVR_DOMAIN,
)
from viseron.components.storage import Storage
from viseron.components.storage.const import COMPONENT as STORAGE_COMPONENT
from viseron.components.storage.models import Events
from viseron.config import load_config
from viseron.const import (
    DOMAIN_FAILED,
    DOMAIN_IDENTIFIERS,
    DOMAIN_LOADED,
    DOMAIN_LOADING,
    DOMAIN_SETUP_TASKS,
    DOMAINS_TO_SETUP,
    ENV_PROFILE_MEMORY,
    EVENT_DOMAIN_REGISTERED,
    FAILED,
    LOADED,
    LOADING,
    REGISTERED_DOMAINS,
    VISERON_SIGNAL_LAST_WRITE,
    VISERON_SIGNAL_SHUTDOWN,
    VISERON_SIGNAL_STOPPING,
)
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.events import Event, EventData
from viseron.exceptions import DataStreamNotLoaded, DomainNotRegisteredError
from viseron.helpers import memory_usage_profiler, utcnow
from viseron.helpers.json import JSONEncoder
from viseron.helpers.logs import (
    DuplicateFilter,
    SensitiveInformationFilter,
    ViseronLogFormat,
)
from viseron.states import States
from viseron.types import SupportedDomains
from viseron.watchdog.subprocess_watchdog import SubprocessWatchDog
from viseron.watchdog.thread_watchdog import ThreadWatchDog

if TYPE_CHECKING:
    from viseron.components.nvr.nvr import NVR
    from viseron.domains.camera import AbstractCamera
    from viseron.domains.face_recognition import AbstractFaceRecognition
    from viseron.domains.image_classification import AbstractImageClassification
    from viseron.domains.license_plate_recognition import (
        AbstractLicensePlateRecognition,
    )
    from viseron.domains.motion_detector import AbstractMotionDetectorScanner
    from viseron.domains.object_detector import AbstractObjectDetector
    from viseron.helpers.entity import Entity

VISERON_SIGNALS = {
    VISERON_SIGNAL_SHUTDOWN: "viseron/signal/shutdown",
    VISERON_SIGNAL_LAST_WRITE: "viseron/signal/last_write",
    VISERON_SIGNAL_STOPPING: "viseron/signal/stopping",
}

SIGNAL_SCHEMA = vol.Schema(
    vol.In(
        VISERON_SIGNALS.keys(),
    )
)

LOGGER = logging.getLogger(f"{__name__}.core")


def enable_logging() -> None:
    """Enable logging."""
    root_logger = logging.getLogger()
    root_logger.propagate = False
    handler = logging.StreamHandler()
    formatter = ViseronLogFormat()
    handler.setFormatter(formatter)
    handler.addFilter(DuplicateFilter())
    handler.addFilter(SensitiveInformationFilter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Silence noisy loggers
    logging.getLogger("apscheduler.scheduler").setLevel(logging.ERROR)
    logging.getLogger("apscheduler.executors").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("tornado.access").setLevel(logging.WARNING)
    logging.getLogger("tornado.application").setLevel(logging.WARNING)
    logging.getLogger("tornado.general").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("watchdog.observers.inotify_buffer").setLevel(logging.WARNING)

    sys.excepthook = lambda *args: logging.getLogger(None).exception(
        "Uncaught exception", exc_info=args  # type: ignore[arg-type]
    )
    threading.excepthook = lambda args: logging.getLogger(None).exception(
        "Uncaught thread exception in thread %s",
        args.thread.name if args.thread else "unknown",
        exc_info=(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        ),  # type: ignore[arg-type]
    )


def setup_viseron() -> Viseron:
    """Set up and run Viseron."""
    start = timer()
    enable_logging()
    viseron_version = os.getenv("VISERON_VERSION")
    LOGGER.info("-------------------------------------------")
    LOGGER.info(f"Initializing Viseron {viseron_version if viseron_version else ''}")

    vis = Viseron()

    try:
        config = load_config()
    except Exception as error:  # pylint: disable=broad-except
        LOGGER.error(
            f"Failed to load config.yaml, activating safe mode: {error}",
            exc_info=error,
        )
        activate_safe_mode(vis)
    else:
        setup_components(vis, config)

    vis.storage = vis.data[STORAGE_COMPONENT]

    if NVR_COMPONENT in vis.data[LOADED]:
        for camera in vis.data[DOMAINS_TO_SETUP].get(CAMERA_DOMAIN, {}).keys():
            if camera not in vis.data[DOMAINS_TO_SETUP].get(NVR_DOMAIN, {}).keys():
                LOGGER.warning(
                    f"Camera with identifier {camera} is not enabled under component "
                    "nvr. This camera will not be processed"
                )
    else:
        nvr_config: dict = {}
        nvr_config["nvr"] = {}
        cameras_to_setup = vis.data[DOMAINS_TO_SETUP].get(CAMERA_DOMAIN, {})
        if cameras_to_setup:
            for camera_to_setup in cameras_to_setup.keys():
                LOGGER.warning(
                    "Manually setting up component nvr with "
                    f"identifier {camera_to_setup}. "
                    "Consider adding it your config.yaml instead"
                )
                nvr_config["nvr"][camera_to_setup] = {}
            setup_component(vis, get_component(vis, NVR_COMPONENT, nvr_config))

    setup_domains(vis)
    vis.setup()

    if vis.safe_mode:
        LOGGER.warning("Viseron is running in safe mode")
    else:
        vis.critical_components_config_store.save(config)

    end = timer()
    LOGGER.info("Viseron initialized in %.1f seconds", end - start)
    return vis


class Viseron:
    """Viseron."""

    def __init__(self) -> None:
        self.states = States(self)

        self.setup_threads: list[threading.Thread] = []

        self.data: dict[str, Any] = {}
        self.data[LOADING] = {}
        self.data[LOADED] = {}
        self.data[FAILED] = {}

        self.data[DOMAIN_LOADING] = {}
        self.data[DOMAIN_LOADED] = {}
        self.data[DOMAIN_FAILED] = {}

        self.data[DOMAINS_TO_SETUP] = {}
        self.data[DOMAIN_SETUP_TASKS] = {}
        self.data[DOMAIN_IDENTIFIERS] = {}
        self._domain_register_lock = threading.Lock()
        self.data[REGISTERED_DOMAINS] = {}

        self._thread_watchdog = ThreadWatchDog()
        self._subprocess_watchdog = SubprocessWatchDog()
        self.background_scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        self.background_scheduler.start()

        self.storage: Storage | None = None

        self.critical_components_config_store = CriticalComponentsConfigStore(self)
        self.safe_mode = False
        self.exit_code = 0
        self.shutdown_stage: Literal["shutdown", "last_write", "stopping"] | None = None

    @property
    def version(self) -> str:
        """Return the version of Viseron."""
        return os.getenv("VISERON_VERSION", "unknown")

    @property
    def git_commit(self) -> str:
        """Return the git commit of Viseron."""
        git_commit = os.getenv("VISERON_GIT_COMMIT")
        if git_commit:
            return git_commit[:7]
        return "unknown"

    def register_signal_handler(self, viseron_signal, callback):
        """Register a callback which gets called on signals emitted by Viseron.

        Signals currently available:
            - shutdown = Emitted when shutdown has been requested
        """
        if DATA_STREAM_COMPONENT not in self.data:
            LOGGER.error(
                f"Failed to register signal handler for {viseron_signal}: "
                f"{DATA_STREAM_COMPONENT} is not loaded"
            )
            return False

        try:
            SIGNAL_SCHEMA(viseron_signal)
        except vol.Invalid as err:
            LOGGER.error(
                f"Failed to register signal handler for {viseron_signal}: {err}"
            )
            return False

        return self.data[DATA_STREAM_COMPONENT].subscribe_data(
            f"viseron/signal/{viseron_signal}", callback
        )

    def listen_event(self, event: str, callback, ioloop=None) -> Callable[[], None]:
        """Register a listener to an event."""
        if DATA_STREAM_COMPONENT not in self.data:
            LOGGER.error(
                f"Failed to register event listener for {event}: "
                f"{DATA_STREAM_COMPONENT} is not loaded"
            )
            raise DataStreamNotLoaded

        data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
        topic = f"event/{event}"
        uuid = data_stream.subscribe_data(topic, callback, ioloop=ioloop)

        def unsubscribe() -> None:
            data_stream.unsubscribe_data(topic, uuid)

        return unsubscribe

    def _insert_event(self, event: Event[EventData]) -> None:
        """Insert event into database."""
        if self.storage:
            event_data_json = "{}"
            if event.data and event.data.json_serializable:
                try:
                    event_data_json = partial(
                        json.dumps, cls=JSONEncoder, allow_nan=False
                    )(event.data)
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    LOGGER.warning(
                        f"Failed to decode event {event.name} to JSON: {error}"
                    )
                    return

            with self.storage.get_session() as session:
                stmt = insert(Events).values(
                    name=event.name,
                    data=event_data_json,
                )
                session.execute(stmt)
                session.commit()

    def dispatch_event(self, event: str, data: EventData, store: bool = True) -> None:
        """Dispatch an event."""
        _event: Event[EventData] = Event(event, data, utcnow().timestamp())
        if store:
            self._insert_event(_event)
        event = f"event/{event}"
        self.data[DATA_STREAM_COMPONENT].publish_data(
            event, data=Event(event, data, time.time())
        )

    @overload
    def register_domain(
        self, domain: Literal["camera"], identifier: str, instance: AbstractCamera
    ) -> None:
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["face_recognition"],
        identifier: str,
        instance: AbstractFaceRecognition,
    ) -> None:
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["image_classification"],
        identifier: str,
        instance: AbstractImageClassification,
    ) -> None:
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["license_plate_recognition"],
        identifier: str,
        instance: AbstractLicensePlateRecognition,
    ) -> None:
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["motion_detector"],
        identifier: str,
        instance: AbstractMotionDetectorScanner,
    ) -> None:
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["object_detector"],
        identifier: str,
        instance: AbstractObjectDetector,
    ) -> None:
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["nvr"],
        identifier: str,
        instance: NVR,
    ) -> None:
        ...

    def register_domain(
        self, domain: SupportedDomains, identifier: str, instance
    ) -> None:
        """Register a domain with a specific identifier."""
        LOGGER.debug(f"Registering domain {domain} with identifier {identifier}")
        with self._domain_register_lock:
            self.data[REGISTERED_DOMAINS].setdefault(domain, {})[identifier] = instance
            self.dispatch_event(
                EVENT_DOMAIN_REGISTERED.format(domain=domain), instance, store=False
            )

    @overload
    def get_registered_domain(
        self, domain: Literal["camera"], identifier: str
    ) -> AbstractCamera:
        ...

    @overload
    def get_registered_domain(
        self, domain: Literal["face_recognition"], identifier: str
    ) -> AbstractFaceRecognition:
        ...

    @overload
    def get_registered_domain(
        self, domain: Literal["image_classification"], identifier: str
    ) -> AbstractImageClassification:
        ...

    @overload
    def get_registered_domain(
        self, domain: Literal["motion_detector"], identifier: str
    ) -> AbstractMotionDetectorScanner:
        ...

    @overload
    def get_registered_domain(
        self, domain: Literal["object_detector"], identifier: str
    ) -> AbstractObjectDetector:
        ...

    @overload
    def get_registered_domain(self, domain: Literal["nvr"], identifier: str) -> NVR:
        ...

    def get_registered_domain(self, domain: SupportedDomains, identifier: str):
        """Return a registered domain with a specific identifier."""
        if (
            domain in self.data[REGISTERED_DOMAINS]
            and identifier in self.data[REGISTERED_DOMAINS][domain]
        ):
            return self.data[REGISTERED_DOMAINS][domain][identifier]

        raise DomainNotRegisteredError(
            domain,
            identifier=identifier,
        )

    @overload
    def get_registered_identifiers(
        self, domain: Literal["camera"]
    ) -> dict[str, AbstractCamera]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["face_recognition"]
    ) -> dict[str, AbstractFaceRecognition]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["image_classification"]
    ) -> dict[str, AbstractImageClassification]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["motion_detector"]
    ) -> dict[str, AbstractMotionDetectorScanner]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["object_detector"]
    ) -> dict[str, AbstractObjectDetector]:
        ...

    @overload
    def get_registered_identifiers(self, domain: Literal["nvr"]) -> dict[str, NVR]:
        ...

    def get_registered_identifiers(self, domain: SupportedDomains):
        """Return a list of all registered identifiers for a domain."""
        if domain in self.data[REGISTERED_DOMAINS]:
            return self.data[REGISTERED_DOMAINS][domain]

        raise DomainNotRegisteredError(
            domain,
        )

    def shutdown(self) -> None:
        """Shut down Viseron."""
        LOGGER.info("Initiating shutdown")

        if self.data.get(DATA_STREAM_COMPONENT, None):
            data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]

        self._thread_watchdog.stop()
        self._subprocess_watchdog.stop()
        try:
            self.background_scheduler.shutdown()
        except SchedulerNotRunningError as err:
            LOGGER.warning(f"Failed to shutdown scheduler: {err}")

        wait_for_threads_and_processes_to_exit(
            self, data_stream, VISERON_SIGNAL_SHUTDOWN
        )
        wait_for_threads_and_processes_to_exit(
            self, data_stream, VISERON_SIGNAL_LAST_WRITE
        )
        wait_for_threads_and_processes_to_exit(
            self, data_stream, VISERON_SIGNAL_STOPPING
        )

        LOGGER.info("Shutdown complete")

    def add_entity(self, component: str, entity: Entity):
        """Add entity to states registry."""
        component_instance = self.data[LOADED].get(component, None)
        if not component_instance:
            component_instance = self.data[LOADING][component]
        return self.states.add_entity(component_instance, entity)

    def add_entities(self, component: str, entities: list[Entity]) -> None:
        """Add entities to states registry."""
        for entity in entities:
            self.add_entity(component, entity)

    def get_entities(self):
        """Return all registered entities."""
        return self.states.get_entities()

    def schedule_periodic_update(self, entity: Entity, update_interval: int) -> None:
        """Schedule entity update at a fixed interval."""
        self.background_scheduler.add_job(
            entity.update, "interval", seconds=update_interval
        )

    def setup(self) -> None:
        """Set up Viseron."""
        if os.getenv(ENV_PROFILE_MEMORY) == "true":
            tracemalloc.start()
            self.background_scheduler.add_job(
                memory_usage_profiler, "interval", seconds=5, args=[LOGGER]
            )


def wait_for_threads_and_processes_to_exit(
    vis: Viseron,
    data_stream: DataStream,
    stage: Literal["shutdown", "last_write", "stopping"],
) -> None:
    """Wait for all threads and processes to exit."""
    vis.shutdown_stage = stage
    data_stream.publish_data(VISERON_SIGNALS[stage])

    LOGGER.debug(f"Waiting for threads and processes to exit in stage {stage}")

    def join(
        thread_or_process: threading.Thread
        | multiprocessing.Process
        | multiprocessing.process.BaseProcess,
    ) -> None:
        thread_or_process.join(timeout=10)
        time.sleep(0.5)  # Wait for process to exit properly
        if thread_or_process.is_alive():
            LOGGER.error(f"{thread_or_process.name} did not exit in time")
            if isinstance(thread_or_process, multiprocessing.Process):
                LOGGER.error(f"Forcefully kill {thread_or_process.name}")
                thread_or_process.kill()

    threads_and_processes: list[
        threading.Thread | multiprocessing.Process | multiprocessing.process.BaseProcess
    ] = [
        thread
        for thread in threading.enumerate()
        if not thread.daemon and thread != threading.current_thread()
    ]
    threads_and_processes += multiprocessing.active_children()

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        thread_or_process_future = {
            executor.submit(join, thread_or_process): thread_or_process
            for thread_or_process in threads_and_processes
            if getattr(thread_or_process, "__stage__", stage) == stage
        }
        for future in concurrent.futures.as_completed(thread_or_process_future):
            future.result()
    LOGGER.debug(f"All threads and processes exited in stage {stage}")
