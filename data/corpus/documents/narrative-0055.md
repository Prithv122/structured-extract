Azure uses the Azure SDK which sets its own user agents. For identity and storage calls you may see respectively strings like these:

- via Azure Identity: `azsdk-cpp-identity/1.11.0 (Darwin 25.2.0 arm64 Darwin Kernel Version 25.2.0: Tue Nov 18 21:07:05 PST 2025; root:xnu-12377.61.12~1/RELEASE_ARM64_T6020 Cpp/201402)`
- via Azure Blob/ADLSv2: `azsdk-cpp-storage-blobs/12.15.0 (Darwin 25.2.0 arm64 Darwin Kernel Version 25.2.0: Tue Nov 18 21:07:05 PST 2025; root:xnu-12377.61.12~1/RELEASE_ARM64_T6020 Cpp/201402)`
