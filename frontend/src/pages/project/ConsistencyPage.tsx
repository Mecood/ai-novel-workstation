import { useParams } from 'react-router-dom';
import { useState } from 'react';
import { Card, Spin, message, Button, Typography, Tag, List, Empty, Alert, Space } from 'antd';
import { ExperimentOutlined, CheckCircleOutlined } from '@ant-design/icons';
import AppLayout from '../../components/layout/AppLayout';
import { aiApi } from '../../services/api';

const { Title, Text } = Typography;

interface ConsistencyIssue {
  severity: string;
  description: string;
  suggestion?: string;
}

interface ConsistencyResult {
  issues: ConsistencyIssue[];
}

const typeColorMap: Record<string, string> = {
  'S1': 'red',
  'S2': 'orange',
  'S3': 'blue',
  'S4': 'purple',
};

export default function ConsistencyPage() {
  const { id } = useParams<{ id: string }>();
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<ConsistencyResult | null>(null);

  const handleCheck = async () => {
    if (!id) return;
    setChecking(true);
    setResult(null);
    try {
      const res = await aiApi.checkConsistency(id);
      const data = typeof res.data.content === 'string' 
        ? JSON.parse(res.data.content) as ConsistencyResult
        : res.data.content as ConsistencyResult;
      setResult(data);
    } catch {
      message.error('一致性检查失败');
    } finally {
      setChecking(false);
    }
  };

  return (
    <AppLayout projectId={id!}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <Title level={3} style={{ margin: 0 }}>
          一致性检查
        </Title>
        <Button
          type="primary"
          icon={<ExperimentOutlined />}
          loading={checking}
          onClick={handleCheck}
        >
          开始检查
        </Button>
      </div>

      {checking && (
        <Card>
          <Spin
            tip="正在检查剧情一致性..."
            style={{ display: 'block', textAlign: 'center', padding: 40 }}
          />
        </Card>
      )}

      {!checking && result && result.issues.length > 0 && (
        <Card
          title={
            <Space>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              检查结果
            </Space>
          }
        >
          <List
            dataSource={result.issues}
            renderItem={(issue) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <Tag color={typeColorMap[issue.severity] || 'default'}>{issue.severity}</Tag>
                      {issue.suggestion && (
                        <Text type="secondary">{issue.suggestion}</Text>
                      )}
                    </Space>
                  }
                  description={issue.description}
                />
              </List.Item>
            )}
          />
        </Card>
      )}

      {!checking && result && result.issues.length === 0 && (
        <Card>
          <Empty description="没有发现不一致之处" />
        </Card>
      )}

      {!checking && !result && (
        <Alert
          type="info"
          message="点击上方按钮开始一致性检查"
          description="AI 将检测剧情矛盾与设定冲突"
          showIcon
        />
      )}
    </AppLayout>
  );
}
