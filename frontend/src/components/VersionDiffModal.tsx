import { useState, useEffect } from 'react';
import { Modal, Select, Spin, Empty } from 'antd';
import { versionApi } from '../services/api';

interface VersionEntry {
  version: number;
  content_hash: string;
  word_count: number;
  saved_at: string;
}

interface VersionDetail {
  version: number;
  content: { text: string };
  saved_at: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  projectId: string;
  chapterId: string;
  versions: VersionEntry[];
}

interface DiffLine {
  type: 'add' | 'del' | 'same';
  text: string;
}

function doDiff(a: string[], b: string[]): DiffLine[] {
  // Simple LCS-based line diff
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i - 1] === b[j - 1] ? dp[i - 1][j - 1] + 1 : Math.max(dp[i - 1][j], dp[i][j - 1]);

  const result: DiffLine[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      result.push({ type: 'same', text: a[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.push({ type: 'add', text: b[j - 1] });
      j--;
    } else {
      result.push({ type: 'del', text: a[i - 1] });
      i--;
    }
  }
  return result.reverse();
}

export default function VersionDiffModal({ open, onClose, projectId, chapterId, versions }: Props) {
  const [verA, setVerA] = useState<number | null>(null);
  const [verB, setVerB] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [linesA, setLinesA] = useState<DiffLine[]>([]);
  const [linesB, setLinesB] = useState<DiffLine[]>([]);
  const [titleA, setTitleA] = useState('');
  const [titleB, setTitleB] = useState('');

  const versionOptions = versions.map(v => ({
    value: v.version,
    label: `版本 ${v.version} — ${v.saved_at?.slice(0, 16) || '未知'} — ${v.word_count || 0}字`,
  }));

  useEffect(() => {
    if (!open) {
      setVerA(null);
      setVerB(null);
      setLinesA([]);
      setLinesB([]);
      return;
    }
    // Default: compare newest two
    if (versions.length >= 2 && verA === null && verB === null) {
      setVerA(versions[0].version);
      setVerB(versions[1].version);
    }
  }, [open, versions]);

  useEffect(() => {
    if (verA == null || verB == null) return;
    setLoading(true);

    const fetchAndDiff = async () => {
      try {
        const [respA, respB] = await Promise.all([
          versionApi.get(projectId, chapterId, verA),
          versionApi.get(projectId, chapterId, verB),
        ]);
        const detailA = respA.data as VersionDetail;
        const detailB = respB.data as VersionDetail;
        const textA = detailA.content?.text || '';
        const textB = detailB.content?.text || '';
        const arrA = textA.split('\n');
        const arrB = textB.split('\n');

        const fullDiff = doDiff(arrA, arrB);

        setLinesA(fullDiff.filter(d => d.type !== 'add'));
        setLinesB(fullDiff.filter(d => d.type !== 'del'));
        setTitleA(`v${verA} — ${detailA.saved_at?.slice(0, 16) || ''}`);
        setTitleB(`v${verB} — ${detailB.saved_at?.slice(0, 16) || ''}`);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    };
    fetchAndDiff();
  }, [verA, verB, projectId, chapterId]);

  const lineStyle = (type: DiffLine['type']): React.CSSProperties => ({
    fontFamily: 'monospace',
    fontSize: 13,
    lineHeight: '1.6',
    padding: '1px 8px',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    background: type === 'del' ? '#fff1f0' : type === 'add' ? '#f6ffed' : undefined,
    borderLeft: type === 'del' ? '3px solid #ff4d4f' : type === 'add' ? '3px solid #52c41a' : undefined,
  });

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title="📝 版本内容对比"
      width={1000}
      footer={null}
    >
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <span>版本 A</span>
        <Select
          style={{ width: 240 }}
          value={verA}
          onChange={setVerA}
          options={versionOptions}
          placeholder="选版本"
        />
        <span>vs</span>
        <Select
          style={{ width: 240 }}
          value={verB}
          onChange={setVerB}
          options={versionOptions}
          placeholder="选版本"
        />
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center' }}>加载中...</div>
      ) : linesA.length || linesB.length ? (
        <div style={{ display: 'flex' }}>
          <div style={{ flex: 1, border: '1px solid #d9d9d9', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{
              background: '#fafafa', padding: '6px 12px', fontWeight: 'bold',
              borderBottom: '1px solid #d9d9d9', fontSize: 13,
            }}>
              {titleA}
            </div>
            <div style={{ maxHeight: 500, overflow: 'auto' }}>
              {linesA.map((l, i) => (
                <div key={i} style={lineStyle(l.type)}>
                  {l.type === 'del' ? '- ' : '  '}{l.text}
                </div>
              ))}
            </div>
          </div>
          <div style={{ flex: 1, border: '1px solid #d9d9d9', borderRadius: 4, overflow: 'hidden', marginLeft: 12 }}>
            <div style={{
              background: '#fafafa', padding: '6px 12px', fontWeight: 'bold',
              borderBottom: '1px solid #d9d9d9', fontSize: 13,
            }}>
              {titleB}
            </div>
            <div style={{ maxHeight: 500, overflow: 'auto' }}>
              {linesB.map((l, i) => (
                <div key={i} style={lineStyle(l.type)}>
                  {l.type === 'add' ? '+ ' : '  '}{l.text}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <Empty description="请选择两个版本进行对比" />
      )}
    </Modal>
  );
}