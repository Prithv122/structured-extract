DuckDB has a [Community Extensions repository]({% link community_extensions/index.md %}), which allows convenient installation of third-party extensions.
Community extension repositories like pip or npm are essentially enabling remote code execution by design. This is less dramatic than it sounds. For better or worse, we are quite used to piping random scripts from the web into our shells, and routinely install a staggering amount of transitive dependencies without thinking twice. Some repositories like CRAN enforce a human inspection at some point, but that’s no guarantee for anything either.

We’ve studied several different approaches to community extension repositories and have picked what we think is a sensible approach: we do not attempt to review the submissions, but require that the *source code of extensions is available*. We do take over the complete build, sign and distribution process. Note that this is a step up from pip and npm that allow uploading arbitrary binaries but a step down from reviewing everything manually. We allow users to [report malicious extensions](https://github.com/duckdb/community-extensions/security/advisories/new) and show adoption statistics like GitHub stars and download count. Because we manage the repository, we can remove problematic extensions from distribution quickly.

Despite this, installing and loading DuckDB extensions from the community extension repository will execute code written by third party developers, and therefore *can* be dangerous. A malicious developer could create and register a harmless-looking DuckDB extension that steals your crypto coins.
If you’re running a web service that executes untrusted SQL from users with DuckDB, we recommend disabling community extensions. To do so, run:

```sql
SET allow_community_extensions = false;
```
