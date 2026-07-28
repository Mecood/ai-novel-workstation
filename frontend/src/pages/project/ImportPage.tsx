import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Upload, Button, Space, message, Typography, Spin, List, Tag, Empty,
} from 'antd';
import { InboxOutlined, FileTextOutlined, BookOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';

const { Dragger } = Upload;
const { Title, Text } = Typography;

interface ParsedChapter {
  index: number; marker: string; marker_type: string;
  title: string; content: string; start_line: number; end_line: number;
}
interface ParseResult {
  filename: string; total_lines: number; chapters: ParsedChapter[];
}

const MARKER_LABELS: Record<string, string> = {
  chapter: '章节', chapter_en: '英文章', volume: '分卷', postscript: '后记',
};
const MARKER_COLORS: Record<string, string> = {
  chapter: 'blue', chapter_en: 'geekblue', volume: 'purple', postscript: 'gold',
};

export default function ImportPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ParseResult | null>(null);
  const [error, setError] = useState('');

  const handleUpload = async (file: File) => {
    setLoading(true); setError(''); setResult(null);
    const form = new FormData(); form.append('file', file);
    try {
      const res = await fetch('/api/v1/importer/parse', { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      const data: ParseResult = await res.json();
      setResult(data);
      message.success(`解析完成：${data.chapters.length} 个章节`);
    } catch (e: any) {
      setError(e.message || '解析失败');
    } finally { setLoading(false); }
    return false;
  };

  const snippet = (ch: ParsedChapter) =>
    ch.content.length > 200 ? ch.content.slice(0, 200) + '……' : ch.content;

  return (
    <AppLayout projectId={projectId}>
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>返回</Button>
          <Title level={4} style={{ margin: 0 }}>导入章节</Title>
        </Space>
        <Text type="secondary">
          上传 .txt 或 .docx 文件，自动识别「第X章」「第X卷」「后记」等标记。
        </Text>

        {!result ? (
          <Card style={{ marginTop: 16 }}>
            <Dragger name="file" accept=".txt,.docx" showUploadList={false}
              beforeUpload={handleUpload} disabled={loading}>
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">
                {loading ? '解析中……' : '点击或拖拽 .txt / .docx 文件'}
              </p>
            </Dragger>
            {loading && <Spin style={{ display: 'block', marginTop: 16 }} />}
            {error && <Text type="danger" style={{ display: 'block', marginTop: 8 }}>{error}</Text>}
          </Card>
        ) : (
          <Card style={{ marginTop: 16 }}
            title={<Space><FileTextOutlined />{result.filename}</Space>}
            extra={<Text type="secondary">{result.total_lines} 行 · {result.chapters.length} 节</Text>}
          >
            {result.chapters.length === 0 ? <Empty description="未识别到章节标记" /> : (
              <List dataSource={result.chapters} renderItem={(ch) => (
                <List.Item>
                  <Card size="small" style={{ width: '100%' }} type="inner"
                    title={
                      <Space>
                        <BookOutlined />
                        <Text strong>{ch.marker}</Text>
                        {ch.title ? <Text type="secondary">{ch.title}</Text> : null}
                        <Tag color={MARKER_COLORS[ch.marker_type] || 'default'}>
                          {MARKER_LABELS[ch.marker_type] || ch.marker_type}
                        </Tag>
                      </Space>
                    }
                  >
                    <Typography.Paragraph
                      type="secondary"
                      style={{ whiteSpace: 'pre-wrap', fontSize: 13, marginBottom: 0 }}
                      ellipsis={{ rows: 4, expandable: true, symbol: '展开' }}
                    >
                      {snippet(ch)}
                    </Typography.Paragraph>
                  </Card>
                </List.Item>
              )} />
            )}
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <Space>
                <Button onClick={() => setResult(null)}>重新上传</Button>
                {projectId && (
                  <Button type="primary"
                    onClick={() => navigate(`/projects/${projectId}/workshop`)}>
                    回到工作台
                  </Button>
                )}
              </Space>
            </div>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}