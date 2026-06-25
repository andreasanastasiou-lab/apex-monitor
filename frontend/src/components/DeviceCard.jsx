import React from 'react';

// TODO: display device name, IP, status, and last-seen timestamp
export default function DeviceCard({ device }) {
  return <div className="device-card">{device?.name ?? 'Unknown device'}</div>;
}
