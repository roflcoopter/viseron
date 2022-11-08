"""Viseron init file."""
from __future__ import annotations

import concurrent.futures
import logging
import multiprocessing
import os
import sys
import threading
import time
import tracemalloc
from dataclasses import dataclass
from timeit import default_timer as timer
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    TypeVar,
    overload,
)

import voluptuous as vol
from apscheduler.schedulers.background import BackgroundScheduler

from viseron.components import (
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
from viseron.config import load_config
from viseron.const import (
    DOMAIN_IDENTIFIERS,
    DOMAIN_SETUP_TASKS,
    DOMAINS_TO_SETUP,
    ENV_PROFILE_MEMORY,
    EVENT_DOMAIN_REGISTERED,
    FAILED,
    LOADED,
    LOADING,
    REGISTERED_DOMAINS,
    VISERON_SIGNAL_SHUTDOWN,
)
from viseron.domains.camera.const import DOMAIN as CAMERA_DOMAIN
from viseron.exceptions import DataStreamNotLoaded, DomainNotRegisteredError
from viseron.helpers import memory_usage_profiler
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
    from viseron.domains.motion_detector import AbstractMotionDetectorScanner
    from viseron.domains.object_detector import AbstractObjectDetector
    from viseron.helpers.entity import Entity

VISERON_SIGNALS = {
    VISERON_SIGNAL_SHUTDOWN: "viseron/signal/shutdown",
}

SIGNAL_SCHEMA = vol.Schema(
    vol.In(
        VISERON_SIGNALS.keys(),
    )
)

LOGGER = logging.getLogger(f"{__name__}.core")


def enable_logging():
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
    logging.getLogger("tornado.access").setLevel(logging.WARNING)
    logging.getLogger("tornado.application").setLevel(logging.WARNING)
    logging.getLogger("tornado.general").setLevel(logging.WARNING)

    sys.excepthook = lambda *args: logging.getLogger(None).exception(
        "Uncaught exception", exc_info=args  # type: ignore
    )
    threading.excepthook = lambda args: logging.getLogger(None).exception(
        "Uncaught thread exception",
        exc_info=(
            args.exc_type,
            args.exc_value,
            args.exc_traceback,
        ),  # type: ignore[arg-type]
    )


def setup_viseron():
    """Set up and run Viseron."""
    start = timer()
    enable_logging()
    LOGGER.info("-------------------------------------------")
    LOGGER.info("Initializing Viseron")

    config = load_config()

    vis = Viseron()

    setup_components(vis, config)

    if NVR_COMPONENT in vis.data[LOADED]:
        for camera in vis.data[DOMAINS_TO_SETUP][CAMERA_DOMAIN].keys():
            if camera not in vis.data[DOMAINS_TO_SETUP][NVR_DOMAIN].keys():
                LOGGER.warning(
                    f"Camera with identifier {camera} is not enabled under component "
                    "nvr. This camera will not be processed"
                )
    else:
        nvr_config = {}
        nvr_config["nvr"] = {}
        for camera_to_setup in vis.data[DOMAINS_TO_SETUP][CAMERA_DOMAIN]:
            LOGGER.warning(
                "Manually setting up component nvr with "
                f"identifier {camera_to_setup}. "
                "Consider adding it your config.yaml instead"
            )
            nvr_config["nvr"][camera_to_setup] = {}
        setup_component(vis, get_component(vis, NVR_COMPONENT, nvr_config))

    setup_domains(vis)
    vis.setup()

    end = timer()
    LOGGER.info("Viseron initialized in %.1f seconds", end - start)
    return vis


T = TypeVar("T")


@dataclass
class Event(Generic[T]):
    """Dataclass that holds an event."""

    name: str
    data: T
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        """Convert Event to dict."""
        return {
            "name": self.name.split("/", 1)[1],
            "data": self.data,
            "timestamp": self.timestamp,
        }


class Viseron:
    """Viseron."""

    def __init__(self):
        self.states = States(self)

        self.setup_threads = []

        self.data = {}
        self.data[LOADING] = {}
        self.data[LOADED] = {}
        self.data[FAILED] = {}

        self.data[DOMAINS_TO_SETUP] = {}
        self.data[DOMAIN_SETUP_TASKS] = {}
        self.data[DOMAIN_IDENTIFIERS] = {}
        self._domain_register_lock = threading.Lock()
        self.data[REGISTERED_DOMAINS] = {}
        self._wait_for_domain_store = {}

        self._thread_watchdog = ThreadWatchDog()
        self._subprocess_watchdog = SubprocessWatchDog()
        self.background_scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        self.background_scheduler.start()

        self.exit_code = 0

    def register_signal_handler(self, viseron_signal, callback):
        """Register a callback which gets called on signals emitted by Viseron.

        Signals currently available:
            - shutdown = Emitted when shutdown has been requested
        """
        if DATA_STREAM_COMPONENT not in self.data[LOADED]:
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

    def listen_event(self, event, callback, ioloop=None) -> Callable[[], None]:
        """Register a listener to an event."""
        if DATA_STREAM_COMPONENT not in self.data[LOADED]:
            LOGGER.error(
                f"Failed to register event listener for {event}: "
                f"{DATA_STREAM_COMPONENT} is not loaded"
            )
            raise DataStreamNotLoaded

        data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
        topic = f"event/{event}"
        uuid = data_stream.subscribe_data(topic, callback, ioloop=ioloop)

        def unsubscribe():
            data_stream.unsubscribe_data(topic, uuid)

        return unsubscribe

    def dispatch_event(self, event, data):
        """Dispatch an event."""
        event = f"event/{event}"
        self.data[DATA_STREAM_COMPONENT].publish_data(
            event, data=Event(event, data, time.time())
        )

    @overload
    def register_domain(
        self, domain: Literal["camera"], identifier: str, instance: AbstractCamera
    ):
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["face_recognition"],
        identifier: str,
        instance: AbstractFaceRecognition,
    ):
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["image_classification"],
        identifier: str,
        instance: AbstractImageClassification,
    ):
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["motion_detector"],
        identifier: str,
        instance: AbstractMotionDetectorScanner,
    ):
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["object_detector"],
        identifier: str,
        instance: AbstractObjectDetector,
    ):
        ...

    @overload
    def register_domain(
        self,
        domain: Literal["nvr"],
        identifier: str,
        instance: NVR,
    ):
        ...

    def register_domain(self, domain: SupportedDomains, identifier: str, instance):
        """Register a domain with a specific identifier."""
        LOGGER.debug(f"Registering domain {domain} with identifier {identifier}")
        with self._domain_register_lock:
            self.data[REGISTERED_DOMAINS].setdefault(domain, {})[identifier] = instance

            if listeners := self._wait_for_domain_store.get(domain, {}).get(
                identifier, None
            ):
                for thread_event in listeners:
                    thread_event.set()
                del self._wait_for_domain_store[domain][identifier]
            self.dispatch_event(EVENT_DOMAIN_REGISTERED.format(domain=domain), instance)

    def wait_for_domain(self, domain: SupportedDomains, identifier: str):
        """Wait for a domain with a specific identifier to register."""
        with self._domain_register_lock:
            if (
                domain in self.data[REGISTERED_DOMAINS]
                and identifier in self.data[REGISTERED_DOMAINS][domain]
            ):
                return self.data[REGISTERED_DOMAINS][domain][identifier]

            LOGGER.debug(
                f"Waiting for domain {domain} with identifier {identifier} to register"
            )
            event = threading.Event()
            self._wait_for_domain_store.setdefault(domain, {}).setdefault(
                identifier, []
            ).append(event)
        event.wait()
        LOGGER.debug(f"Done waiting for domain {domain} with identifier {identifier}")
        return self.data[REGISTERED_DOMAINS][domain][identifier]

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
    ) -> Dict[str, AbstractCamera]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["face_recognition"]
    ) -> Dict[str, AbstractFaceRecognition]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["image_classification"]
    ) -> Dict[str, AbstractImageClassification]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["motion_detector"]
    ) -> Dict[str, AbstractMotionDetectorScanner]:
        ...

    @overload
    def get_registered_identifiers(
        self, domain: Literal["object_detector"]
    ) -> Dict[str, AbstractObjectDetector]:
        ...

    @overload
    def get_registered_identifiers(self, domain: Literal["nvr"]) -> Dict[str, NVR]:
        ...

    def get_registered_identifiers(self, domain: SupportedDomains):
        """Return a list of all registered identifiers for a domain."""
        if domain in self.data[REGISTERED_DOMAINS]:
            return self.data[REGISTERED_DOMAINS][domain]

        raise DomainNotRegisteredError(
            domain,
        )

    def shutdown(self):
        """Shut down Viseron."""
        LOGGER.info("Initiating shutdown")

        if self.data.get(DATA_STREAM_COMPONENT, None):
            data_stream: DataStream = self.data[DATA_STREAM_COMPONENT]
            data_stream.publish_data(VISERON_SIGNALS["shutdown"])

        self._thread_watchdog.stop()
        self._subprocess_watchdog.stop()
        self.background_scheduler.shutdown()

        def join(thread_or_process: threading.Thread | multiprocessing.Process):
            thread_or_process.join(timeout=8)
            time.sleep(0.5)  # Wait for process to exit properly
            if thread_or_process.is_alive():
                LOGGER.error(f"{thread_or_process.name} did not exit in time")
                if isinstance(thread_or_process, multiprocessing.Process):
                    LOGGER.error(f"Forcefully kill {thread_or_process.name}")
                    thread_or_process.kill()

        threads_and_processes: List[threading.Thread | multiprocessing.Process] = [
            thread
            for thread in threading.enumerate()
            if not thread.daemon and thread != threading.current_thread()
        ]
        threads_and_processes += multiprocessing.active_children()

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            thread_or_process_future = {
                executor.submit(join, thread_or_process): thread_or_process
                for thread_or_process in threads_and_processes
            }
            for future in concurrent.futures.as_completed(thread_or_process_future):
                future.result()
        LOGGER.info("Shutdown complete")

    def add_entity(self, component: str, entity: Entity):
        """Add entity to states registry."""
        component_instance = self.data[LOADED].get(component, None)
        if not component_instance:
            component_instance = self.data[LOADING][component]
        self.states.add_entity(component_instance, entity)

    def add_entities(self, component: str, entities: List[Entity]):
        """Add entities to states registry."""
        for entity in entities:
            self.add_entity(component, entity)

    def get_entities(self):
        """Return all registered entities."""
        return self.states.get_entities()

    def schedule_periodic_update(self, entity: Entity, update_interval: int):
        """Schedule entity update at a fixed interval."""
        self.background_scheduler.add_job(
            entity.update, "interval", seconds=update_interval
        )

    def setup(self):
        """Set up Viseron."""
        if os.getenv(ENV_PROFILE_MEMORY) == "true":
            tracemalloc.start()
            self.background_scheduler.add_job(
                memory_usage_profiler, "interval", seconds=5, args=[LOGGER]
            )
