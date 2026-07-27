import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import { Button, Divider } from 'antd';
import {
  BoldOutlined,
  ItalicOutlined,
  UnderlineOutlined,
  StrikethroughOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
  UndoOutlined,
  RedoOutlined,
} from '@ant-design/icons';

interface TiptapEditorProps {
  value: string;                    // plain text in
  onChange: (text: string) => void; // plain text out
  editable?: boolean;
  height?: number;
}

const TiptapEditor: React.FC<TiptapEditorProps> = ({
  value,
  onChange,
  editable = true,
  height = 500,
}) => {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
    ],
    content: value,
    editable,
    onUpdate: ({ editor }) => {
      // Extract plain text — key constraint: backend stores {text: "..."}
      const text = editor.getText();
      onChange(text);
    },
    editorProps: {
      attributes: {
        style: `min-height: ${height}px; height: auto; overflow-y: auto; padding: 12px 16px; outline: none;`,
      },
    },
  });

  // Sync external value changes (e.g., selecting a different chapter)
  // Only update when the plain text differs to avoid cursor jumps
  if (editor && editor.getText() !== value) {
    // Use a microtask to avoid flushSync warnings during render
    queueMicrotask(() => {
      if (editor.getText() !== value) {
        editor.commands.setContent(value);
      }
    });
  }

  if (!editor) return null;

  return (
    <div
      style={{
        border: '1px solid #d9d9d9',
        borderRadius: '6px',
        overflow: 'hidden',
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 4,
          padding: '6px 8px',
          borderBottom: '1px solid #d9d9d9',
          background: '#fafafa',
        }}
      >
        {/* Bold */}
        <Button
          size="small"
          type={editor.isActive('bold') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleBold().run()}
          icon={<BoldOutlined />}
        />
        {/* Italic */}
        <Button
          size="small"
          type={editor.isActive('italic') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleItalic().run()}
          icon={<ItalicOutlined />}
        />
        {/* Underline */}
        <Button
          size="small"
          type={editor.isActive('underline') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          icon={<UnderlineOutlined />}
        />
        {/* Strike */}
        <Button
          size="small"
          type={editor.isActive('strike') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleStrike().run()}
          icon={<StrikethroughOutlined />}
        />

        <Divider type="vertical" style={{ borderColor: '#d9d9d9' }} />

        {/* H1 */}
        <Button
          size="small"
          type={editor.isActive('heading', { level: 1 }) ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          style={{ fontWeight: 700, fontSize: 14 }}
        >
          H1
        </Button>
        {/* H2 */}
        <Button
          size="small"
          type={editor.isActive('heading', { level: 2 }) ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          style={{ fontWeight: 600 }}
        >
          H2
        </Button>
        {/* H3 */}
        <Button
          size="small"
          type={editor.isActive('heading', { level: 3 }) ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
          style={{ fontWeight: 500 }}
        >
          H3
        </Button>

        <Divider type="vertical" style={{ borderColor: '#d9d9d9' }} />

        {/* Blockquote */}
        <Button
          size="small"
          type={editor.isActive('blockquote') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleBlockquote().run()}
          style={{ fontFamily: 'serif', fontWeight: 600 }}
        >
          ❝
        </Button>
        {/* Bullet List */}
        <Button
          size="small"
          type={editor.isActive('bulletList') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          icon={<UnorderedListOutlined />}
        />
        {/* Ordered List */}
        <Button
          size="small"
          type={editor.isActive('orderedList') ? 'primary' : 'text'}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          icon={<OrderedListOutlined />}
        />

        <Divider type="vertical" style={{ borderColor: '#d9d9d9' }} />

        {/* Undo */}
        <Button
          size="small"
          type="text"
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          icon={<UndoOutlined />}
        />
        {/* Redo */}
        <Button
          size="small"
          type="text"
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          icon={<RedoOutlined />}
        />
      </div>

      {/* Editor content */}
      <EditorContent editor={editor} />
    </div>
  );
};

export default TiptapEditor;