import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Card, Button, List, message, Spin, Typography, Popconfirm, Space, Tag, Divider } from 'antd';
import { ExportOutlined, FileTextOutlined, CloudDownloadOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { chapterApi, exportApi } from '../../services/api';
import type { Chapter } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

export default function ExportPage() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [projectName, setProjectName] = useState('');
  const [exporting, setExporting] = useState<string | null>(null); // 'full' | chapterId

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    chapterApi.list(id).then(({ data }) => {
      const list = Array.isArray(data) ? data : [];
      setChapters(list);
    }).catch(() => message.error('加载章节失败'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    fetch(`/api/v1/projects/${id}`)
      .then(r => r.json()).then(d => setProjectName(d.name || '未命名项目'))
      .catch(() => setProjectName('未命名'));
  }, [id]);

  const downloadFull = async () => {
    if (!id) return;
    setExporting('full');
    try {
      await exportApi.downloadFull(id, projectName);
      message.success('全本导出成功');
    } catch (e: any) {
      message.error('导出失败: ' + (e.message || '未知错误'));
    } finally {
      setExporting(null);
    }
  };

  const downloadChapter = async (chapterId: string, title: string) => {
    if (!id) return;
    setExporting(chapterId);
    try {
      await exportApi.downloadChapter(id, projectName, chapterId, title);
      message.success(`「${title}」导出成功`);
    } catch (e: any) {
      message.error('导出失败: ' + (e.message || '未知错误'));
    } finally {
      setExporting(null);
    }
  };

  return (
    <AppLayout projectId={id!}>
      <Title level={3}><ExportOutlined style={{ marginRight: 8 }} />导出</Title>
      <Paragraph type="secondary">
        将小说导出为 .docx 文件，可整本或分章下载。
      </Paragraph>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
          <Spin size="large" />
        </div>
      ) : (
        <Card
          title={projectName}
          extra={
            <Popconfirm
              title={`整本导出为 ${projectName}.docx？`}
              onConfirm={downloadFull}
              okText="导出"
              cancelText="取消"
            >
              <Button
                type="primary"
                icon={<CloudDownloadOutlined />}
                loading={exporting === 'full'}
              >
                导出整本
              </Button>
            </Popconfirm>
          }
        >
          <Divider orientation="left">分章导出（共 {chapters.length} 章）</Divider>
          <List
            dataSource={chapters}
            renderItem={ch => (
              <List.Item>
                <Space>
                  <FileTextOutlined style={{ color: '#5B9BD5' }} />
                  <Text strong>{ch.title}</Text>
                  <Tag color="blue">{ch.chapter_number}</Tag>
                  <Text type="secondary">{ch.word_count || 0} 字</Text>
                </Space>
                <Button
                  icon={<ExportOutlined />}
                  onClick={() => downloadChapter(ch.id, ch.title)}
                  loading={exporting === ch.id}
                >
                  导出本章
                </Button>
              </List.Item>
            )}
          />
        </Card>
      )}
    </AppLayout>
  );
}