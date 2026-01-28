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
        self._onvif_device_service: Any = None  # ONVIF Device service instance
        self._device_capabilities: Any = None  # to store Device capabilities

    async def initialize(self) -> None:
        """Initialize the Device/Core service."""
        self._onvif_device_service = self._client.devicemgmt()
        self._device_capabilities = await self.get_service_capabilities()

        if not self._auto_config and self._config:
            await self.apply_config()

    # ## The Real Operations ## #

    # ---- Capabilities Operations ---- #

    @operation()
    async def get_service_capabilities(self) -> Any:
        """Get Device service capabilities."""
        return self._onvif_device_service.GetServiceCapabilities()

    @operation()
    async def get_services(self) -> Any:
        """Get available services on the device."""
        return self._onvif_device_service.GetServices(IncludeCapability=False)

    # ---- System Operations ---- #

    @operation()
    async def get_device_information(self) -> Any:
        """Get device information."""
        return self._onvif_device_service.GetDeviceInformation()

    @operation()
    async def get_scopes(self) -> Any:
        """Get device scopes."""
        return self._onvif_device_service.GetScopes()

    @operation()
    async def add_scopes(self, scopes: list[str]) -> bool:
        """Add device scopes."""
        self._onvif_device_service.AddScopes(ScopeItem=scopes)
        return True

    @operation()
    async def set_scopes(self, scopes: list[str]) -> bool:
        """Set device scopes."""
        self._onvif_device_service.SetScopes(Scopes=scopes)
        return True

    @operation()
    async def remove_scopes(self, scopes: list[str]) -> bool:
        """Remove device scopes."""
        self._onvif_device_service.RemoveScopes(ScopeItem=scopes)
        return True

    @operation()
    async def system_reboot(self) -> bool:
        """Reboot the device."""
        LOGGER.warning(f"Rebooting ONVIF camera for {self._camera.identifier}")
        self._onvif_device_service.SystemReboot()
        return True

    @operation()
    async def system_factory_default(self, level: str) -> bool:
        """Restore the device to factory default settings."""
        LOGGER.warning(
            f"Restoring ONVIF camera to factory default for {self._camera.identifier}"
        )
        self._onvif_device_service.SetSystemFactoryDefault(FactoryDefault=level)
        return True

    # ---- Date & Time Operations ---- #

    @operation()
    async def get_system_date_and_time(self) -> Any:
        """Get system date and time from the device."""
        return self._onvif_device_service.GetSystemDateAndTime()

    @operation()
    async def set_system_date_and_time(
        self,
        datetime_type: str = "NTP",
        daylight_savings: bool | None = None,
        timezone: str | None = None,
        utc_datetime: dict[str, Any] | None = None,
    ) -> bool:
        """Set system date and time."""
        timezone_param = {"TZ": timezone} if timezone else None
        self._onvif_device_service.SetSystemDateAndTime(
            DateTimeType=datetime_type,
            DaylightSavings=daylight_savings,
            TimeZone=timezone_param,
            UTCDateTime=utc_datetime,
        )
        return True

    # ---- Security Operations ---- #

    @operation()
    async def get_users(self) -> Any:
        """Get device users."""
        return self._onvif_device_service.GetUsers()

    @operation()
    async def create_users(self, users: list[dict[str, Any]]) -> bool:
        """Create device users."""
        self._onvif_device_service.CreateUsers(User=users)
        return True

    @operation()
    async def delete_users(self, username: str) -> bool:
        """Delete device user."""
        self._onvif_device_service.DeleteUsers(Username=username)
        return True

    @operation()
    async def set_user(self, users: list[dict[str, Any]]) -> bool:
        """Set device users."""
        self._onvif_device_service.SetUser(User=users)
        return True

    # ---- Network Operations ---- #

    @operation()
    async def get_hostname(self) -> Any:
        """Get device hostname."""
        return self._onvif_device_service.GetHostname()

    @operation()
    async def set_hostname(self, hostname: str | None = None) -> bool:
        """Set device hostname."""
        self._onvif_device_service.SetHostname(Name=hostname)
        return True

    @operation()
    async def set_hostname_from_dhcp(self, from_dhcp: bool) -> bool:
        """Set device hostname from DHCP."""
        self._onvif_device_service.SetHostnameFromDHCP(FromDHCP=from_dhcp)
        return True

    @operation()
    async def get_discovery_mode(self) -> Any:
        """Get discovery mode."""
        return self._onvif_device_service.GetDiscoveryMode()

    @operation()
    async def set_discovery_mode(self, discoverable: bool) -> bool:
        """Set discovery mode."""
        mode = "Discoverable" if discoverable else "NonDiscoverable"
        self._onvif_device_service.SetDiscoveryMode(DiscoveryMode=mode)
        return True

    @operation()
    async def get_ntp(self) -> Any:
        """Get NTP configuration."""
        return self._onvif_device_service.GetNTP()

    @operation()
    async def set_ntp(
        self,
        from_dhcp: bool,
        ntp_type: str | None = None,
        ntp_server: str | None = None,
    ) -> bool:
        """Set NTP configuration."""
        ntp_manual = None
        if ntp_server and ntp_type:
            match ntp_type:
                case "DNS":
                    ntp_manual = {"Type": ntp_type, "DNSname": ntp_server}
                case "IPv4":
                    ntp_manual = {"Type": ntp_type, "IPv4Address": ntp_server}
                case "IPv6":
                    ntp_manual = {"Type": ntp_type, "IPv6Address": ntp_server}
                case _:
                    return False
        self._onvif_device_service.SetNTP(FromDHCP=from_dhcp, NTPManual=ntp_manual)
        return True

    @operation()
    async def get_network_default_gateway(self) -> Any:
        """Get network default gateway."""
        return self._onvif_device_service.GetNetworkDefaultGateway()

    @operation()
    async def set_network_default_gateway(
        self, ipv4_address: str | None = None, ipv6_address: str | None = None
    ) -> bool:
        """Set network default gateway."""
        self._onvif_device_service.SetNetworkDefaultGateway(
            IPv4Address=ipv4_address, IPv6Address=ipv6_address
        )
        return True

    @operation()
    async def get_network_protocols(self) -> Any:
        """Get network protocols."""
        return self._onvif_device_service.GetNetworkProtocols()

    @operation()
    async def set_network_protocols(
        self, network_protocols: list[dict[str, Any]]
    ) -> bool:
        """Set network protocols."""
        self._onvif_device_service.SetNetworkProtocols(
            NetworkProtocols=network_protocols
        )
        return True

    @operation()
    async def get_network_interfaces(self) -> Any:
        """Get network interfaces."""
        return self._onvif_device_service.GetNetworkInterfaces()

    @operation()
    async def set_network_interfaces(
        self, interface_token: str, network_interface: dict[str, Any]
    ) -> bool:
        """Set network interfaces."""
        self._onvif_device_service.SetNetworkInterfaces(
            InterfaceToken=interface_token, NetworkInterface=network_interface
        )
        return True

    @operation()
    async def get_dns(self) -> Any:
        """Get network DNS."""
        return self._onvif_device_service.GetDNS()

    @operation()
    async def set_dns(
        self,
        from_dhcp: bool,
        search_domain: str | None = None,
        dns_manual: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Set network DNS."""
        self._onvif_device_service.SetDNS(
            FromDHCP=from_dhcp, SearchDomain=search_domain, DNSManual=dns_manual
        )
        return True

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
