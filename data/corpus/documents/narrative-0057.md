Register the CSV text as a file, then load it with `insertCSVFromPath()`. The insert options describe the target table and, when auto-detection is disabled, the CSV dialect and column types:

```ts
import { Int32, Utf8 } from 'apache-arrow';

const csvContent = '1|foo\n2|bar\n';
await db.registerFileText('data.csv', csvContent);

await conn.insertCSVFromPath('data.csv', {
    schema: 'main',
    name: 'foo',
    detect: false,
    header: false,
    delimiter: '|',
    columns: {
        col1: new Int32(),
        col2: new Utf8(),
    },
});
```
