// @ts-nocheck
import { useCallback, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Card,
  Input,
  Button,
  Spin,
  Tag,
  Typography,
  Row,
  Col,
  Space,
  Collapse,
  Alert,
  List,
  Empty,
  Select,
  Checkbox,
  Statistic,
  message,
} from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  CloudUploadOutlined,
  FileTextOutlined,
  GlobalOutlined,
  TeamOutlined,
  BookOutlined,
  QuestionCircleOutlined,
  SyncOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { searchApi } from '../../services/api';

const { Title, Paragraph, Text } = Typography;
const { Search: SearchInput } = Input;
const { Option } = Select;

type ContentType = 'chapters' | 'worldview' | 'characters' | 'knowledge';

type SearchResult = Record<string, unknown>;

const contentMeta: Record<
  ContentType,
  { key: ContentType; label: string; color: string; icon: React.ReactNode }
> = {
  chapters: {
    key: 'chapters',
    label: '章节内容',
    color: '#5B9BD5',
    icon: <FileTextOutlined />,
  },
  worldview: {
    key: 'worldview',
    label: '世界观设定',
    color: '#70AD47',
    icon: <GlobalOutlined />,
  },
  characters: {
    key: 'characters',
    label: '角色设定',
    color: '#9B59B6',
    icon: <TeamOutlined />,
  },
  knowledge: {
    key: 'knowledge',
    label: '知识库',
    color: '#FA8C16',
    icon: <BookOutlined />,
  },
};

function formatChapter(result: Record<string, unknown>) {
  const meta = (result.metadata ?? {}) as Record<string, unknown>;
  const chapter = meta.chapter ?? meta.chapter_number ?? result.chapter ?? result.chapter_number;
  const title = meta.title ?? result.title;
  if (!chapter && !title) return null;
  const chapterText = typeof chapter === 'number' || Number.isFinite(Number(chapter)) ? `第${Number(chapter)}章` : '全文';
  const titleText = title ? ` · ${title}` : '';
  return chapterText + titleText;
}


function sourceMeta(result: Record<string, unknown>) {
  const raw = result as SearchResult;
  const sourceType = String(
    raw.source_type ??
      ((raw.metadata as { source_type?: string } | undefined)?.source_type ?? ''),
  ).toLowerCase();
  const meta = (raw.metadata ?? {}) as Record<string, unknown>;
  const metaType = String(meta.source_type ?? '').toLowerCase();
  const key = (sourceType || metaType) as ContentType;
  const item = contentMeta[key];
  const label = item?.label || metaType || '内容';
  return { label, color: item?.color ?? '#5B9BD5', icon: item?.icon ?? <FolderOpenOutlined /> };
}

function formatSource(result: Record<string, unknown>) {
  return sourceMeta(result).label;
}

export default function SearchPage() {
  const { id } = useParams<{ id: string }>();
  const [query, setQuery] = useState('');
  const [top_k, setTopK] = useState<number>(5);
  const [use_rerank, setUseRerank] = useState(true);
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<unknown[]>([]);
  const [total, setTotal] = useState(0);
  const [contextTopic, setContextTopic] = useState('');
  const [context, setContext] = useState('');
  const [contextLoading, setContextLoading] = useState(false);
  const [collapsedIndex, setCollapsedIndex] = useState(['index']);
  const [indexing, setIndexing] = useState<ContentType | null>(null);
  const [lastIndexed, setLastIndexed] = useState<Record<string, string | null>>({
    chapters: null,
    worldview: null,
    characters: null,
    knowledge: null,
  });

  const searchContent = useCallback(async () => {
    if (!id || !query.trim()) return;
    setSearching(true);
    try {
      const res = await searchApi.search(id, query.trim(), top_k, use_rerank);
      setResults(Array.isArray(res.data.results) ? res.data.results : []);
      setTotal(typeof res.data.total === 'number' ? res.data.total : results.length);
    } catch {
      message.error('搜索失败，请检查后端或索引状态');
      setResults([]);
      setTotal(0);
    } finally {
      setSearching(false);
    }
  }, [id, query, top_k, use_rerank]);

  const getContext = useCallback(async () => {
    if (!id || !contextTopic.trim()) return;
    setContextLoading(true);
    try {
      const res = await searchApi.getContext(id, contextTopic.trim());
      setContext(typeof res.data?.context === 'string' ? res.data.context : JSON.stringify(res.data, null, 2));
    } catch {
      message.error('上下文检索失败，请检查后端或索引状态');
      setContext('');
    } finally {
      setContextLoading(false);
    }
  }, [id, contextTopic]);

  const indexOne = useCallback(
    async (type: ContentType) => {
      if (!id) return;
      setIndexing(type);
      try {
        const res = await searchApi.indexContent(id, type);
        const time = new Date().toLocaleTimeString();
        setLastIndexed((prev) => ({ ...prev, [type]: `${res.data?.indexed ?? '?'} 条 · ${time}` }));
        message.success(`${contentMeta[type].label}索引完成`);
      } catch {
        message.error(`${contentMeta[type].label}索引失败`);
      } finally {
        setIndexing(null);
      }
    },
    [id],
  );

  const indexAll = useCallback(async () => {
    const order: ContentType[] = ['chapters', 'worldview', 'characters', 'knowledge'];
    for (const type of order) {
      await indexOne(type);
    }
  }, [indexOne]);

  const handleIndexKeyChange = (keys: string | string[]) => setCollapsedIndex(Array.isArray(keys) ? keys : keys ? [keys] : []);

  return (
    <AppLayout projectId={id || undefined}>
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <SearchOutlined style={{ color: '#5B9BD5', marginRight: 8 }} />
          项目搜索与索引
        </Title>
        <Paragraph type="secondary" style={{ marginTop: 8 }}>
          对章节、世界观、角色、知识库进行语义检索，并可重新构建向量索引以优化搜索结果。
        </Paragraph>
      </div>

      <Card
        title="语义搜索"
        extra={
          <Text type="secondary" style={{ fontSize: 12 }}>
            Top K：{top_k}，Rerank：{use_rerank ? '开启' : '关闭'}
          </Text>
        }
        style={{ marginBottom: 24, borderLeft: '4px solid #5B9BD5' }}
        bodyStyle={{ padding: '20px 24px' }}
      >
        <Row gutter={[12, 12]} align="middle">
          <Col flex="1 1 600px">
            <SearchInput
              placeholder="输入你想查找的内容，例如：主角性格、伏笔、世界观规则、某章情节"
              allowClear
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onPressEnter={searchContent}
              prefix={<SearchOutlined style={{ color: '#5B9BD5' }} />}
            />
          </Col>
          <Col span={12} sm={6}>
            <Select value={top_k} onChange={setTopK} style={{ width: 120 }}>
              <Option value={3}>Top 3</Option>
              <Option value={5}>Top 5</Option>
              <Option value={10}>Top 10</Option>
              <Option value={20}>Top 20</Option>
            </Select>
          </Col>
          <Col span={12} sm={6}>
            <Checkbox checked={use_rerank} onChange={(e) => setUseRerank(e.target.checked)}>
              开启 Rerank
            </Checkbox>
          </Col>
          <Col>
            <Button type="primary" icon={<SearchOutlined />} loading={searching} onClick={searchContent}>
              搜索
            </Button>
          </Col>
        </Row>
      </Card>

      <Card
        title={`搜索结果${results.length > 0 ? `（共 ${total} 条）` : ''}`}
        bodyStyle={{ padding: 0 }}
        style={{ marginBottom: 24 }}
      >
        {searching ? (
          <div style={{ textAlign: 'center', padding: 64 }}>
            <Spin size="large" tip="正在检索..." />
          </div>
        ) : results.length === 0 ? (
          <div style={{ padding: 64 }}>
            <Empty
              description={
                <Space direction="vertical" size={12}>
                  <Text type="secondary">先在索引管理中完成向量索引，再输入查询词搜索</Text>
                  <Alert
                    type="info"
                    message="提示：索引 chapters/worldview/characters/knowledge 可提升搜索命中率和上下文相关性"
                    showIcon
                  />
                </Space>
              }
            />
          </div>
        ) : (
          <List
            itemLayout="horizontal"
            dataSource={results}
            locale={{ emptyText: null }}
            renderItem={(item) => {
              const result = item as Record<string, unknown>;
              const snippet =
                String(result.snippet ?? result.content ?? result.text ?? result.summary ?? '').slice(0, 260);
              const meta = sourceMeta(result);
              const chapter = formatChapter(result);
              const score = Number(result.score ?? result.distance ?? 0);

              return (
                <List.Item>
                  <div style={{ width: '100%' }}>
                    <Space size={[8, 4]} wrap style={{ marginBottom: 8 }}>
                      <Tag color={meta.color}>
                        {meta.icon} {meta.label}
                      </Tag>
                      {chapter && (
                        <Tag color="processing">
                          <FileTextOutlined style={{ marginRight: 4 }} />
                          {chapter}
                        </Tag>
                      )}
                      {Number.isFinite(score) && <Tag>相似度 {score.toFixed(3)}</Tag>}
                    </Space>
                    <Paragraph style={{ margin: 0, color: '#333', fontSize: 14, lineHeight: 1.7 }}>
                      {snippet || '无可用文本片段'}
                    </Paragraph>
                  </div>
                </List.Item>
              );
            }}
          />
        )}
      </Card>

      <Collapse activeKey={collapsedIndex} onChange={handleIndexKeyChange} ghost style={{ marginBottom: 24 }}>
        <Collapse.Panel
          header={
            <Space>
              <CloudUploadOutlined style={{ color: '#5B9BD5' }} />
              <Title level={5} style={{ margin: 0 }}>
                索引管理
              </Title>
              <Text type="secondary" style={{ fontSize: 12 }}>
                向量索引将影响语义搜索和上下文检索效果
              </Text>
            </Space>
          }
          key="index"
        >
          <Card size="small" bodyStyle={{ padding: 20 }}>
            <Row gutter={[16, 16]}>
              <Col span={24} sm={12}>
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Title level={5}>索引状态</Title>
                  <Statistic title="章节内容" value={lastIndexed.chapters || '未索引'} valueStyle={{ color: lastIndexed.chapters ? '#5B9BD5' : '#8c8c8c' }} />
                  <Statistic title="世界观" value={lastIndexed.worldview || '未索引'} valueStyle={{ color: lastIndexed.worldview ? '#70AD47' : '#8c8c8c' }} />
                  <Statistic title="角色" value={lastIndexed.characters || '未索引'} valueStyle={{ color: lastIndexed.characters ? '#9B59B6' : '#8c8c8c' }} />
                  <Statistic title="知识库" value={lastIndexed.knowledge || '未索引'} valueStyle={{ color: lastIndexed.knowledge ? '#FA8C16' : '#8c8c8c' }} />
                </Space>
              </Col>
              <Col span={24} sm={12}>
                <Title level={5}>索引操作</Title>
                <Card size="small">
                  <Button
                    block
                    type="primary"
                    icon={<SyncOutlined spin={indexing !== null} />}
                    onClick={indexAll}
                    disabled={indexing !== null}
                  >
                    索引全部类型
                  </Button>
                </Card>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
                    或按类型分别索引
                  </Text>
                  <Row gutter={[8, 8]}>
                    {Object.values(contentMeta).map(({ key, label, color, icon }) => (
                      <Col span={12} key={key}>
                        <Button
                          block
                          type="dashed"
                          icon={icon}
                          loading={indexing === key}
                          style={{ borderColor: color, color }}
                          onClick={() => indexOne(key)}
                        >
                          {label}
                        </Button>
                      </Col>
                    ))}
                  </Row>
                </div>
                <Alert
                  type="info"
                  showIcon
                  style={{ marginTop: 12 }}
                  message="索引说明"
                  description="索引按钮会读取项目当前内容并写入向量库；重新搜索前建议至少索引章节内容。"
                />
              </Col>
            </Row>
          </Card>
        </Collapse.Panel>
      </Collapse>

      <Card
        title="上下文检索"
        extra={
          <Tag color="#5B9BD5" icon={<QuestionCircleOutlined />}>
            写作前获取相关上下文
          </Tag>
        }
        style={{ borderLeft: '4px solid #5B9BD5' }}
        bodyStyle={{ padding: '20px 24px' }}
      >
        <Row gutter={[12, 12]} align="middle" style={{ marginBottom: 16 }}>
          <Col flex="1 1 600px">
            <Input
              placeholder="输入章节主题，例如：主角第一次进入修仙学院、家族宴会的冲突、反派登场"
              value={contextTopic}
              onChange={(e) => setContextTopic(e.target.value)}
              onPressEnter={getContext}
              disabled={contextLoading}
            />
          </Col>
          <Col>
            <Button
              type="primary"
              icon={contextLoading ? <Spin size="small" /> : <ReloadOutlined />}
              loading={contextLoading}
              onClick={getContext}
            >
              获取上下文
            </Button>
          </Col>
        </Row>
        {context ? (
          <Card
            size="small"
            bordered
            style={{ background: '#F8FBFF' }}
            bodyStyle={{ whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.8 }}
          >
            {context}
          </Card>
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="输入主题后点击获取上下文，结果会展示在下方"
          />
        )}
      </Card>
    </AppLayout>
  );
}
