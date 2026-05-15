# IPv6 Support in Zapret DNS Settings

## Overview

Zapret now supports IPv6 DNS configuration, allowing users to set both IPv4 and IPv6 DNS servers for their network adapters. This feature provides better compatibility with modern networks and improved DNS resolution for IPv6-enabled services.

## Features

### 1. Dual-Stack DNS Configuration

Users can now configure both IPv4 and IPv6 DNS servers simultaneously:
- **IPv4 DNS**: Traditional DNS servers using IPv4 addresses (e.g., `8.8.8.8`, `1.1.1.1`)
- **IPv6 DNS**: Modern DNS servers using IPv6 addresses (e.g., `2001:4860:4860::8888`, `2606:4700:4700::1111`)

### 2. IPv6 Connectivity Detection

The application automatically detects IPv6 connectivity availability:
- Checks if the network adapter supports IPv6
- Tests connectivity to IPv6 DNS servers
- Displays real-time status indicator in the UI

### 3. IPv6 Address Validation

Built-in validation ensures correct IPv6 format:
- Uses Python's `ipaddress.IPv6Address` class for validation
- Catches malformed addresses before applying to registry
- Provides visual feedback for invalid entries

### 4. Registry Integration

IPv6 DNS settings are stored in the Windows registry:
- **IPv4 Path**: `Tcpip\Parameters\Interfaces\{GUID}`
- **IPv6 Path**: `Tcpip6\Parameters\Interfaces\{GUID}`

## User Interface

### Custom DNS Section

The custom DNS card now includes IPv6 input fields:

```
[✓] Свой: [8.8.8.8] [208.67.222.222] IPv6: [2001:4860:4860::8888] [2620:119:35::35] [OK] 🟢 IPv6
```

**Components:**
- **IPv4 Primary**: First IPv4 DNS server
- **IPv4 Secondary**: Second IPv4 DNS server (optional)
- **IPv6 Primary**: First IPv6 DNS server
- **IPv6 Secondary**: Second IPv6 DNS server (optional)
- **Status Indicator**: Shows IPv6 connectivity status (🟢 available, ⚫ unavailable)

### IPv6 Status Indicator

The IPv6 status indicator provides visual feedback:

- **🟢 Green Check (✓)**: IPv6 is available from your ISP
  - Tooltip: "IPv6 доступен"
  - Label: "IPv6"

- **⚫ Gray X (✗)**: IPv6 is not available from your ISP
  - Tooltip: "IPv6 недоступен от провайдера"
  - Label: (empty)

## Supported DNS Providers

All DNS providers in the application include IPv6 addresses:

### Popular DNS Providers

| Provider | IPv4 | IPv6 | Description |
|----------|------|------|-------------|
| Cloudflare | 1.1.1.1, 1.0.0.1 | 2606:4700:4700::1111, 2606:4700:4700::1001 | Быстрый и приватный |
| Google DNS | 8.8.8.8, 8.8.4.4 | 2001:4860:4860::8888, 2001:4860:4860::8844 | Надёжный |
| Dns.SB | 185.222.222.222, 45.11.45.11 | 2a09::, 2a11:: | Без цензуры |

### Secure DNS Providers

| Provider | IPv4 | IPv6 | Description |
|----------|------|------|-------------|
| Quad9 | 9.9.9.9, 149.112.112.112 | 2620:fe::fe, 2620:fe::9 | Антивирус |
| AdGuard | 94.140.14.14, 94.140.15.15 | 2a10:50c0::ad1:ff, 2a10:50c0::ad2:ff | Без рекламы |
| OpenDNS | 208.67.222.222, 208.67.220.220 | 2620:119:35::35, 2620:119:53::53 | Фильтрация |

### AI-Unblocking DNS

| Provider | IPv4 | IPv6 | Description |
|----------|------|------|-------------|
| dns.malw.link | 84.21.189.133, 64.188.98.242 | 2a12:bec4:1460:d5::2, 2a01:ecc0:2c1:2::2 | ChatGPT |

## Technical Implementation

### Backend Architecture

**DNSManager.set_custom_dns()** method supports IPv6 through the `address_family` parameter:

```python
def set_custom_dns(
    self,
    adapter_name: str,
    primary_dns: str,
    secondary_dns: Optional[str] = None,
    address_family: str = "IPv4"  # "IPv4" or "IPv6"
) -> Tuple[bool, str]:
    """Sets custom DNS via registry"""
    guid = self.get_adapter_guid(adapter_name)
    if not guid:
        return False, "GUID not found"
    
    dns_list = [primary_dns]
    if secondary_dns:
        dns_list.append(secondary_dns)
    
    is_ipv6 = (address_family.lower() == "ipv6")
    success = set_dns_via_registry(guid, dns_list, is_ipv6)
    
    if success:
        if not is_ipv6:
            # DoH only applies to IPv4
            normalized_primary = (primary_dns or "").strip()
            if normalized_primary:
                template = get_doh_template_for_dns(normalized_primary)
                if template:
                    set_doh_for_adapter(guid, normalized_primary, enable=True)
        notify_dns_change()
        return True, "OK"
    else:
        return False, "Registry update failed"
```

### IPv6 Connectivity Check

**DNSForceManager.check_ipv6_connectivity()** tests IPv6 availability:

```python
@staticmethod
def check_ipv6_connectivity() -> bool:
    """Quick IPv6 connectivity test"""
    try:
        # Try to create IPv6 socket
        sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        sock.settimeout(1)
        try:
            sock.connect(('2001:4860:4860::8888', 53))
            sock.close()
            return True
        except:
            sock.close()
            return False
    except:
        return False
```

### IPv6 Validation

The UI validates IPv6 addresses using Python's `ipaddress` module:

```python
@staticmethod
def _is_valid_ipv6(address: str) -> bool:
    """Validates IPv6 address format"""
    import ipaddress
    try:
        ipaddress.IPv6Address(address)
        return True
    except (ValueError, ipaddress.AddressValueError):
        return False
```

## Usage Guide

### Setting Custom IPv6 DNS

1. **Open Network Settings**
   - Launch Zapret application
   - Navigate to "Сеть" (Network) page

2. **Enable Custom DNS**
   - Click on the "Свой" (Custom) DNS card
   - The card will be highlighted with an orange indicator

3. **Enter IPv6 Addresses**
   - In the IPv6 fields, enter your preferred DNS servers:
     - Primary: `2001:4860:4860::8888` (Google)
     - Secondary: `2620:119:35::35` (OpenDNS)

4. **Apply Changes**
   - Click "OK" or press Enter
   - The application will validate and apply both IPv4 and IPv6 DNS
   - DNS cache will be flushed automatically

### Verifying IPv6 DNS

After applying custom DNS:

1. Check the adapter card shows both IPv4 and IPv6:
   ```
   v4 8.8.8.8, 8.8.4.4 | v6 2001:4860:4860::8888, 2620:119:35::35
   ```

2. Use Windows command line to verify:
   ```cmd
   ipconfig /all
   ```
   Look for "DNS Servers" section showing both IPv4 and IPv6 addresses.

3. Test IPv6 connectivity:
   ```cmd
   ping -6 2001:4860:4860::8888
   ```

## Troubleshooting

### IPv6 Status Shows "Unavailable"

**Symptoms:**
- Gray X icon next to IPv6 fields
- Tooltip: "IPv6 недоступен от провайдера"

**Causes:**
1. Your ISP doesn't provide IPv6 connectivity
2. Network adapter doesn't support IPv6
3. Windows IPv6 stack is disabled

**Solutions:**
1. Contact your ISP to enable IPv6
2. Check adapter properties in Windows Network Settings
3. Ensure "Internet Protocol Version 6 (TCP/IPv6)" is enabled

### Invalid IPv6 Address Format

**Symptoms:**
- DNS not applying after clicking OK
- Warning in log: "Неверный формат IPv6"

**Valid IPv6 Formats:**
- ✓ `2001:4860:4860::8888` (compressed)
- ✓ `2606:4700:4700::1111` (compressed)
- ✓ `fe80::1%eth0` (with zone ID)

**Invalid IPv6 Formats:**
- ✗ `2001:4860:4860:0000:0000:0000:0000:8888` (too verbose, use compression)
- ✗ `2001:4860::8888::1` (multiple :: not allowed)
- ✗ `8.8.8.8` (this is IPv4, not IPv6)

### DNS Not Applying

**Symptoms:**
- Adapter card still shows old DNS after applying

**Solutions:**
1. Run Zapret as Administrator
2. Flush DNS cache manually:
   ```cmd
   ipconfig /flushdns
   ```
3. Disable and re-enable network adapter
4. Check Windows Event Viewer for registry errors

## Migration from IPv4-Only

If you previously used IPv4-only DNS:

1. **No Action Required**: IPv4 DNS continues to work as before
2. **Optional Enhancement**: Add IPv6 DNS for dual-stack support
3. **Automatic Detection**: App will detect IPv6 availability automatically
4. **Backward Compatible**: All existing configurations remain valid

## Future Enhancements

Potential future improvements:

1. **IPv6-Only Mode**: Support for IPv6-only network configurations
2. **DNS-over-HTTPS for IPv6**: DoH templates for IPv6 addresses
3. **IPv6 Prefix Detection**: Auto-detect IPv6 prefix from adapter
4. **RA/DHCPv6 Support**: Router Advertisement and DHCPv6 integration
5. **IPv6 Connectivity Test Page**: Dedicated diagnostic tool

## References

- [RFC 4291 - IPv6 Addressing Architecture](https://tools.ietf.org/html/rfc4291)
- [Windows IPv6 Documentation](https://docs.microsoft.com/en-us/windows/win32/winsock/ipv6-2)
- [Python ipaddress Module](https://docs.python.org/3/library/ipaddress.html)
- [DNS Providers with IPv6](https://www.privacytools.io/providers/dns/)
