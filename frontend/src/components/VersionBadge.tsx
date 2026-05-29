import { useState } from 'react';
import { Tag, Dropdown, Button, Alert, message } from 'antd';
import { HistoryOutlined, WarningOutlined, UndoOutlined } from '@ant-design/icons';

interface VersionHistoryEntry {
  version: number;
  created_at: string;
  based_on?: Record<string, number>;
  data?: any;
}

interface VersionBadgeProps {
  version: number;
  stale: boolean;
  history: VersionHistoryEntry[];
  onRestore: (version: number) => Promise<void>;
  basedOn?: Record<string, number>;
  upstreamVersions?: Record<string, number>;
}

export default function VersionBadge({
  version,
  stale,
  history,
  onRestore,
  basedOn,
  upstreamVersions,
}: VersionBadgeProps) {
  const [restoring, setRestoring] = useState(false);

  const handleRestore = async (v: number) => {
    setRestoring(true);
    try {
      await onRestore(v);
      message.success(`已回退到版本 ${v}`);
    } catch {
      message.error('回退失败');
    } finally {
      setRestoring(false);
    }
  };

  const historyItems = (history || []).map((h) => ({
    key: String(h.version),
    label: (
      <div style={{ minWidth: 200 }}>
        <div>
          <Tag color="default">v{h.version}</Tag>
          <span style={{ fontSize: 12, color: '#999' }}>
            {h.created_at ? new Date(h.created_at).toLocaleString('zh-CN') : ''}
          </span>
        </div>
        {h.based_on && Object.keys(h.based_on).length > 0 && (
          <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
            基于：{Object.entries(h.based_on).map(([k, v]) => `${k}=v${v}`).join(', ')}
          </div>
        )}
        <Button
          type="link"
          size="small"
          icon={<UndoOutlined />}
          onClick={() => handleRestore(h.version)}
          loading={restoring}
          style={{ padding: 0, marginTop: 4 }}
        >
          回退到此版本
        </Button>
      </div>
    ),
  }));

  // Check if based_on has outdated upstream
  let outdatedUpstream: string[] = [];
  if (basedOn && upstreamVersions) {
    for (const [key, ver] of Object.entries(basedOn)) {
      const currentVer = upstreamVersions[key] || 0;
      if (currentVer > ver) {
        outdatedUpstream.push(key);
      }
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <Tag color={stale ? 'orange' : 'blue'} style={{ margin: 0 }}>
        v{version}
        {stale && ' ⚠️'}
      </Tag>

      {historyItems.length > 0 && (
        <Dropdown menu={{ items: historyItems }} placement="bottomRight">
          <Button size="small" type="text" icon={<HistoryOutlined />} style={{ fontSize: 12 }}>
            历史 ({historyItems.length})
          </Button>
        </Dropdown>
      )}

      {stale && (
        <Tag color="warning" icon={<WarningOutlined />}>
          上游已变化，建议重新生成
        </Tag>
      )}
    </div>
  );
}
