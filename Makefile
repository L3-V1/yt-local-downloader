MAKEFLAGS+="-j 2"

.PHONY: dev

dev:
	.\.env\Scripts\activate && uvicorn main:app --reload --host 0.0.0.0 --port 5000