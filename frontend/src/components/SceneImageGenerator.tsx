// SceneImageGenerator — AI scene image generation component
// Renders a collapsible panel with image display + prompt input + generate button
// @ts-nocheck

import { useState, useEffect, useCallback } from 'react';
import { Button, Card, Input, Image, Modal, Space, Spin, Typography, message } from 'antd';
import { PictureOutlined, ThunderboltOutlined, ExpandOutlined } from '@ant-design/icons';
import { assetsApi } from '../services/api';

const { TextArea } = Input;
const { Text } = Typography;

interface SceneAsset {
  id: string;
  url: string;
  label: string;
  prompt: string;
  created_at: string;
}

interface Props {
  projectId: string;
}

export default function SceneImageGenerator({ projectId }: Props) {
  const [assets, setAssets] = useState<SceneAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [label, setLabel] = useState('');
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewSrc, setPreviewSrc] = useState('');
  const [expanded, setExpanded] = useState(true);

  // Fetch existing assets
  const fetchAssets = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const { data } = await assetsApi.list(projectId);
      setAssets(data?.items || []);
    } catch {
      // Silently ignore — assets are optional
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  // Load on mount
  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  // Generate a new scene image
  const handleGenerate = async () => {
    if (!prompt.trim()) {
      message.warning('请输入场景描述');
      return;
    }
    setGenerating(true);
    try {
      const { data } = await assetsApi.generateScene(projectId, {
        prompt: prompt.trim(),
        label: label.trim() || '场景图',
      });
      setAssets((prev) => [data, ...prev]);
      setPrompt('');
      setLabel('');
      message.success('场景图生成完成');
    } catch (err: any) {
      message.error(err?.message || '生成失败');
    } finally {
      setGenerating(false);
    }
  };

  // Build full image URL (prepend the Vite proxy base for dev)
  const fullUrl = (path: string) => {
    if (path.startsWith('/static/')) {
      return `http://localhost:9000${path}`;
    }
    return path;
  };

  return (
    <Card
      size="small"
      title={
        <Space>
          <PictureOutlined />
          <Text strong>场景图生成</Text>
        </Space>
      }
      extra={
        <Button
          type="text"
          size="small"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '收起' : '展开'}
        </Button>
      }
      style={{ marginBottom: 16 }}
    >
      {expanded && (
        <>
          {/* Prompt input area */}
          <Space direction="vertical" style={{ width: '100%', marginBottom: 12 }}>
            <Input
              placeholder="场景图标签（可选）"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              size="small"
              style={{ width: '100%' }}
            />
            <TextArea
              placeholder="描述你想要生成的场景，例如：青云山顶，云雾缭绕的仙门大殿，飞瀑流泉..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              style={{ width: '100%' }}
            />
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={generating}
              onClick={handleGenerate}
              block
              disabled={!prompt.trim()}
            >
              生成场景图
            </Button>
          </Space>

          {/* Image gallery */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Spin tip="加载中..." />
            </div>
          ) : assets.length === 0 ? (
            <Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 16 }}>
              暂无条件图
            </Text>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {assets.map((asset) => (
                <div
                  key={asset.id}
                  style={{
                    position: 'relative',
                    width: 120,
                    height: 120,
                    borderRadius: 8,
                    overflow: 'hidden',
                    cursor: 'pointer',
                    border: '1px solid #f0f0f0',
                  }}
                  onClick={() => {
                    setPreviewSrc(fullUrl(asset.url));
                    setPreviewVisible(true);
                  }}
                >
                  <Image
                    src={fullUrl(asset.url)}
                    alt={asset.label || asset.prompt}
                    preview={false}
                    style={{
                      width: 120,
                      height: 120,
                      objectFit: 'cover',
                    }}
                    fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIwIiBoZWlnaHQ9IjEyMCIgIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGcgZmlsbD0iI2U4ZThlOCI+PHBhdGggZD0iTTAgMGgxMjB2MTIWRIV6IiAvPjxwb2x5Z29uIHBvaW50cz0iMTIwLDEyMCAwLDEyMCAwLDAgNjAsNiAxM/AsNjAiIG9wYWNpdHk9Ii4zIiAvPjxwb2x5Z29uIHBvaW50cz0iMCwwIDEyMCwwIDEyMCwxMjAiIG9wYWNpdHk9Ii4yIiAvPjwvZz48L3N2Zz4="
                  />
                  <ExpandOutlined
                    style={{
                      position: 'absolute',
                      top: 4,
                      right: 4,
                      color: '#fff',
                      fontSize: 14,
                      textShadow: '0 1px 3px rgba(0,0,0,0.6)',
                    }}
                  />
                  {asset.label && (
                    <Text
                      style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        backgroundColor: 'rgba(0,0,0,0.55)',
                        color: '#fff',
                        fontSize: 11,
                        padding: '2px 6px',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {asset.label}
                    </Text>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Full-size preview modal */}
          <Modal
            open={previewVisible}
            footer={null}
            onCancel={() => setPreviewVisible(false)}
            width="auto"
            centered
            style={{ maxWidth: '90vw' }}
          >
            <Image src={previewSrc} style={{ maxWidth: '100%', maxHeight: '80vh' }} preview={false} />
          </Modal>
        </>
      )}
    </Card>
  );
}