"""Device (Core) service management for ONVIF component."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from onvif import ONVIFClient

from .const import (
    CONFIG_DEVICE_DATETIME_TYPE,
    CONFIG_DEVICE_DAYLIGHT_SAVINGS,
    CONFIG_DEVICE_DISCOVERABLE,
    CONFIG_DEVICE_HOSTNAME,
    CONFIG_DEVICE_NTP_FROM_DHCP,
    CONFIG_DEVICE_NTP_SERVER,
    CONFIG_DEVICE_NTP_TYPE,
    CONFIG_DEVICE_TIMEZONE,
)
from .utils import operation

if TYPE_CHECKING:
    from viseron.domains.camera import AbstractCamera

LOGGER = logging.getLogger(__name__)


class Device:
    """Class for managing Device (Core) operations for an ONVIF camera."""

    def __init__(
        self,
        camera: AbstractCamera,
        client: ONVIFClient,
        config: dict[str, Any],
        auto_config: bool = True,
    ) -> None:
        self._camera = camera
        self._client = client
        self._config = config
        self._auto_config = auto_config
        self._device_service: Any = None

    async def initialize(self) -> None:
        """Initialize the Device/Core service."""
        self._device_service = self._client.devicemgmt()

        if not self._auto_config and self._config:
            await self.apply_config()

    # ## The Real Operations ## #

    # ---- System Operations ---- #

    @operation()
    async def get_capabilities(self) -> Any:
        """Get device capabilities."""
        return self._device_service.GetCapabilities(Category="All")

    @operation()
    async def get_services(self) -> Any:
        """Get available services on the device."""
        return self._device_service.GetServices(IncludeCapability=False)

    @operation()
    async def get_device_information(self) -> Any:
        """Get device information."""
        return self._device_service.GetDeviceInformation()

    @operation()
    async def get_discovery_mode(self) -> Any:
        """Get discovery mode."""
        return self._device_service.GetDiscoveryMode()

    @operation()
    async def set_discovery_mode(self, discoverable: bool | None = None) -> bool:
        """Set discovery mode."""
        if not self._auto_config and discoverable is None:
            discoverable = self._config.get(CONFIG_DEVICE_DISCOVERABLE, True)

        mode = "Discoverable" if discoverable else "NonDiscoverable"
        self._device_service.SetDiscoveryMode(DiscoveryMode=mode)

        return True

    @operation()
    async def get_scopes(self) -> Any:
        """Get device scopes."""
        return self._device_service.GetScopes()

    @operation()
    async def add_scopes(self, scopes: list[str]) -> bool:
        """Add device scopes."""
        self._device_service.AddScopes(Scopes=scopes)
        return True

    @operation()
    async def set_scopes(self, scopes: list[str]) -> bool:
        """Set device scopes."""
        self._device_service.SetScopes(Scopes=scopes)
        return True

    @operation()
    async def remove_scopes(self, scopes: list[str]) -> bool:
        """Remove device scopes."""
        self._device_service.RemoveScopes(Scopes=scopes)
        return True

    @operation()
    async def system_reboot(self) -> bool:
        """Reboot the device."""
        LOGGER.warning(f"Rebooting ONVIF camera for {self._camera.identifier}")
        self._device_service.SystemReboot()

        return True

    # ---- Date & Time Operations ---- #

    @operation()
    async def get_system_date_and_time(self) -> Any:
        """Get system date and time from the device."""
        return self._device_service.GetSystemDateAndTime()

    @operation()
    async def set_system_date_and_time(
        self,
        datetime_type: str = "NTP",
        daylight_savings: bool | None = None,
        timezone: str | None = None,
    ) -> bool:
        """Set system date and time."""
        daylight_savings = daylight_savings or self._config.get(
            CONFIG_DEVICE_DAYLIGHT_SAVINGS
        )

        # Timezone is ignored if datetime_type is NTP
        timezone_param = None
        if datetime_type != "NTP":
            timezone = timezone or self._config.get(CONFIG_DEVICE_TIMEZONE)
            timezone_param = {"TZ": timezone} if timezone else None

        self._device_service.SetSystemDateAndTime(
            DateTimeType=datetime_type,
            DaylightSavings=daylight_savings,
            TimeZone=timezone_param,
        )

        return True

    # ---- Security Operations ---- #

    @operation()
    async def get_users(self) -> Any:
        """Get device users."""
        return self._device_service.GetUsers()

    @operation()
    async def create_users(self, user: dict[str, Any]) -> Any:
        """Create device users."""
        return self._device_service.CreateUsers(User=user)

    @operation()
    async def delete_users(self, usernames: list[str]) -> bool:
        """Delete device users."""
        self._device_service.DeleteUsers(Usernames=usernames)
        return True

    @operation()
    async def set_user(self, user: dict[str, Any]) -> bool:
        """Set device user."""
        self._device_service.SetUser(User=user)
        return True

    # ---- Network Operations ---- #

    @operation()
    async def get_hostname(self) -> Any:
        """Get device hostname."""
        return self._device_service.GetHostname()

    @operation()
    async def set_hostname(self, hostname: str | None = None) -> Any:
        """Set device hostname."""
        self._device_service.SetHostname(Name=hostname)
        return True

    @operation()
    async def get_ntp(self) -> Any:
        """Get NTP configuration."""
        return self._device_service.GetNTP()

    @operation()
    async def set_ntp(
        self,
        ntp_server: str | None = None,
        from_dhcp: bool | None = None,
        ntp_type: str | None = None,
    ) -> bool:
        """Set NTP configuration."""
        if not self._auto_config and from_dhcp is None:
            from_dhcp = self._config.get(CONFIG_DEVICE_NTP_FROM_DHCP, False)

        ntp_manual = None
        if not from_dhcp:
            if not self._auto_config and ntp_server is None:
                ntp_server = self._config.get(CONFIG_DEVICE_NTP_SERVER)
            if ntp_server:
                match ntp_type:
                    case "DNS":
                        ntp_manual = {"Type": ntp_type, "DNSname": ntp_server}
                    case "IPv4":
                        ntp_manual = {"Type": ntp_type, "IPv4Address": ntp_server}
                    case "IPv6":
                        ntp_manual = {"Type": ntp_type, "IPv6Address": ntp_server}
                    case _:
                        return False

        self._device_service.SetNTP(FromDHCP=from_dhcp, NTPManual=ntp_manual)

        return True

    @operation()
    async def get_network_default_gateway(self) -> Any:
        """Get network interfaces."""
        return self._device_service.GetNetworkDefaultGateway()

    @operation()
    async def get_network_interfaces(self) -> Any:
        """Get network interfaces."""
        return self._device_service.GetNetworkInterfaces()

    @operation()
    async def get_network_protocols(self) -> Any:
        """Get network protocols."""
        return self._device_service.GetNetworkProtocols()

    @operation()
    async def get_dns(self) -> Any:
        """Get network DNS."""
        return self._device_service.GetDNS()

    # ## Apply Configuration at Startup ## #

    async def apply_config(self) -> bool:
        """Apply all configured device settings from config."""
        try:
            if CONFIG_DEVICE_DISCOVERABLE in self._config:
                await self.set_discovery_mode(self._config[CONFIG_DEVICE_DISCOVERABLE])

            if CONFIG_DEVICE_HOSTNAME in self._config:
                await self.set_hostname(self._config[CONFIG_DEVICE_HOSTNAME])

            ntp_server = self._config.get(CONFIG_DEVICE_NTP_SERVER)
            ntp_from_dhcp = self._config.get(CONFIG_DEVICE_NTP_FROM_DHCP)
            ntp_type = self._config.get(CONFIG_DEVICE_NTP_TYPE)
            if ntp_server or ntp_from_dhcp is not None:
                await self.set_ntp(
                    ntp_server=ntp_server, from_dhcp=ntp_from_dhcp, ntp_type=ntp_type
                )

            datetime_type = self._config.get(CONFIG_DEVICE_DATETIME_TYPE)
            daylight_savings = self._config.get(CONFIG_DEVICE_DAYLIGHT_SAVINGS)
            timezone = self._config.get(CONFIG_DEVICE_TIMEZONE)
            if datetime_type or timezone or daylight_savings is not None:
                await self.set_system_date_and_time(
                    datetime_type=datetime_type,
                    daylight_savings=daylight_savings,
                    timezone=timezone,
                )

            LOGGER.info(
                f"Device service configuration for {self._camera.identifier} "
                f"has been applied."
            )
        except (ValueError, AttributeError) as error:
            LOGGER.error(
                f"Error applying Device service configuration for "
                f"{self._camera.identifier}: {error}"
            )
            return False
        return True
