.PHONY: build test publish \
	build_go test_go \
	build_nodejs test_nodejs publish_nodejs \
	build_python test_python build_dist_python publish_python \
	build_java test_java publish_java \
	build_dotnet test_dotnet pack_dotnet publish_dotnet

build: build_go build_nodejs build_python build_java build_dotnet
test: test_go test_nodejs test_python test_java test_dotnet
publish: publish_nodejs publish_python publish_java publish_dotnet

build_go:
	cd go && go build ./... && go vet ./...
test_go:
	cd go && go test ./...

build_nodejs:
	cd nodejs && npm ci && npm run build
test_nodejs:
	cd nodejs && npm test
# --tag latest is explicit because the same-day release scheme produces a
# hyphenated version (<y>.<m>.<d>-post<HHMM>), which semver reads as a
# prerelease; npm then refuses to apply the latest tag implicitly.
publish_nodejs:
	cd nodejs && npm ci && npm run build && npm pkg set version=$(VERSION) && npm publish --tag latest

build_python:
	cd python && python3 -m venv .venv && .venv/bin/pip install --upgrade pip build && .venv/bin/python -m build .
test_python:
	cd python && python3 -m unittest discover -s tests -v
build_dist_python:
	cd python && rm -rf dist *.egg-info && python3 -m venv .venv && \
		.venv/bin/pip install --upgrade pip build toml-cli && \
		.venv/bin/toml set --toml-path pyproject.toml project.version $(VERSION) && \
		.venv/bin/python -m build .
publish_python: build_dist_python
	cd python && .venv/bin/pip install --upgrade twine && .venv/bin/twine upload dist/*

build_java:
	cd java && ./gradlew --console=plain build -x test
test_java:
	cd java && ./gradlew --console=plain test
publish_java:
	cd java && PACKAGE_VERSION=$(VERSION) ./gradlew --console=plain \
		publishToSonatype closeAndReleaseSonatypeStagingRepository

build_dotnet:
	cd dotnet && dotnet build
test_dotnet:
	cd dotnet && dotnet test
pack_dotnet:
	cd dotnet && PACKAGE_VERSION=$(VERSION) dotnet pack Pulumi.Cloud.Sdk.csproj -c Release -o nupkg
publish_dotnet: pack_dotnet
	cd dotnet && dotnet nuget push "nupkg/*.nupkg" --api-key $(NUGET_PUBLISH_KEY) \
		--source https://api.nuget.org/v3/index.json --skip-duplicate
