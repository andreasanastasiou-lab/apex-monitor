import datetime

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    getCmd,
    usmAesCfb128Protocol,
    usmHMACSHAAuthProtocol,
    usmNoAuthProtocol,
    usmNoPrivProtocol,
)

# Frequently polled OIDs — callers may pass any valid OID string instead.
COMMON_OIDS = {
    "cpu_load":      "1.3.6.1.4.1.2021.10.1.3.1",
    "memory_used":   "1.3.6.1.4.1.2021.4.6.0",
    "if_in_octets":  "1.3.6.1.2.1.2.2.1.10",
    "if_out_octets": "1.3.6.1.2.1.2.2.1.16",
    "sys_uptime":    "1.3.6.1.2.1.1.3.0",
    "sys_name":      "1.3.6.1.2.1.1.5.0",
}


def snmp_get(
    host: str,
    oid: str,
    community: str = None,
    version: int = 2,
    v3_user: str = None,
    v3_auth: str = None,
    v3_priv: str = None,
) -> dict:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        if version == 3:
            if not v3_user:
                raise ValueError("v3_user is required for SNMPv3")
            if v3_auth and v3_priv:
                auth_data = UsmUserData(
                    v3_user,
                    authKey=v3_auth,
                    privKey=v3_priv,
                    authProtocol=usmHMACSHAAuthProtocol,
                    privProtocol=usmAesCfb128Protocol,
                )
            elif v3_auth:
                auth_data = UsmUserData(
                    v3_user,
                    authKey=v3_auth,
                    authProtocol=usmHMACSHAAuthProtocol,
                    privProtocol=usmNoPrivProtocol,
                )
            else:
                auth_data = UsmUserData(
                    v3_user,
                    authProtocol=usmNoAuthProtocol,
                    privProtocol=usmNoPrivProtocol,
                )
        else:
            # SNMPv2c (mpModel=1) or SNMPv1 (mpModel=0)
            mp_model = 0 if version == 1 else 1
            auth_data = CommunityData(community or "public", mpModel=mp_model)

        error_indication, error_status, error_index, var_binds = next(
            getCmd(
                SnmpEngine(),
                auth_data,
                UdpTransportTarget((host, 161), timeout=5, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        )

        if error_indication:
            return {
                "host": host,
                "oid": oid,
                "value": None,
                "timestamp": timestamp,
                "error": str(error_indication),
            }

        if error_status:
            return {
                "host": host,
                "oid": oid,
                "value": None,
                "timestamp": timestamp,
                "error": f"{error_status.prettyPrint()} at index {error_index}",
            }

        value = var_binds[0][1].prettyPrint()
        return {
            "host": host,
            "oid": oid,
            "value": value,
            "timestamp": timestamp,
            "error": None,
        }

    except Exception as e:
        return {
            "host": host,
            "oid": oid,
            "value": None,
            "timestamp": timestamp,
            "error": str(e),
        }
