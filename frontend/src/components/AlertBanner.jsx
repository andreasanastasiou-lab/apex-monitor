import React from 'react';

// TODO: display active alerts from /api/alerts
export default function AlertBanner({ alerts = [] }) {
  if (alerts.length === 0) return null;
  return (
    <div className="alert-banner">
      {alerts.length} active alert{alerts.length !== 1 ? 's' : ''}
    </div>
  );
}
