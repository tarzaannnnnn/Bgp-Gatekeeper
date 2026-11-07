BADASS     := python3 tests/badass.py
LAB        := badass-gns3-lab
STAMP_DIR  := .make

HOST_STAMP   := $(STAMP_DIR)/alpine-host.stamp
ROUTER_STAMP := $(STAMP_DIR)/alpine-router.stamp
LAB_STAMP    := $(STAMP_DIR)/lab-image.stamp

HOST_SRCS    := $(shell find P1/host -type f 2>/dev/null)
ROUTER_SRCS  := $(shell find P1/router -type f 2>/dev/null)
LAB_SRCS     := $(shell find tests/gns3-lab -type f 2>/dev/null)

C_RESET  := \033[0m
C_BOLD   := \033[1m
C_CYAN   := \033[36m
C_GREEN  := \033[32m
C_YELLOW := \033[33m
C_RED    := \033[31m
C_DIM    := \033[2m

.DEFAULT_GOAL := help
.PHONY: help images lab lab-down p1 p2 p3 p2-static p2-group p3-hosts
.PHONY: stop status test test-p1 test-p2 test-p3 clean fclean prune

help:
	@printf "\n$(C_BOLD)$(C_CYAN)  ⚡ BADASS GNS3 LAB CONTROLLER ⚡$(C_RESET)\n"
	@printf "$(C_DIM)  ──────────────────────────────────────────────────────$(C_RESET)\n"
	@printf "  $(C_BOLD)$(C_YELLOW)CORE & LAB$(C_RESET)\n"
	@printf "    $(C_GREEN)make images$(C_RESET)       Build host & router images (cached)\n"
	@printf "    $(C_GREEN)make lab$(C_RESET)          Build & launch GNS3 server container\n"
	@printf "    $(C_GREEN)make lab-down$(C_RESET)     Stop & remove GNS3 server container\n\n"
	@printf "  $(C_BOLD)$(C_YELLOW)TOPOLOGIES$(C_RESET)\n"
	@printf "    $(C_GREEN)make p1 | p2 | p3$(C_RESET) Build & start topology (if changed)\n"
	@printf "    $(C_GREEN)make p2-static$(C_RESET)    Switch P2 to static routing mode\n"
	@printf "    $(C_GREEN)make p2-group$(C_RESET)     Switch P2 to multicast group mode\n"
	@printf "    $(C_GREEN)make p3-hosts$(C_RESET)     Configure P3 hosts\n"
	@printf "    $(C_GREEN)make status$(C_RESET)       Show active topology status\n"
	@printf "    $(C_GREEN)make stop$(C_RESET)         Tear down all running topologies\n\n"
	@printf "  $(C_BOLD)$(C_YELLOW)TESTING$(C_RESET)\n"
	@printf "    $(C_GREEN)make test$(C_RESET)         Run full test suite (P1, P2, P3)\n"
	@printf "    $(C_GREEN)make test-p[1-3]$(C_RESET)  Run tests for a single topology\n\n"
	@printf "  $(C_BOLD)$(C_YELLOW)CLEANUP$(C_RESET)\n"
	@printf "    $(C_RED)make clean$(C_RESET)        Remove containers, images & stamps\n"
	@printf "    $(C_RED)make fclean$(C_RESET)       Clean + prune build cache & pycache\n"
	@printf "    $(C_RED)make prune$(C_RESET)        Nuclear wipe of all Docker resources\n"
	@printf "$(C_DIM)  ──────────────────────────────────────────────────────$(C_RESET)\n\n"

images: $(HOST_STAMP) $(ROUTER_STAMP)

$(HOST_STAMP): $(HOST_SRCS)
	@mkdir -p $(STAMP_DIR)
	docker build -t alpine-host P1/host
	@touch $@

$(ROUTER_STAMP): $(ROUTER_SRCS)
	@mkdir -p $(STAMP_DIR)
	docker build -t alpine-router P1/router
	@touch $@

$(LAB_STAMP): $(LAB_SRCS)
	@mkdir -p $(STAMP_DIR)
	docker build -t $(LAB) tests/gns3-lab
	@touch $@

lab: $(LAB_STAMP)
	@if [ -z "$$(docker ps -q -f name=^/$(LAB)$$)" ]; then \
		docker start $(LAB) 2>/dev/null || \
		docker run -d --privileged --name $(LAB) -p 127.0.0.1:13080:3080 $(LAB); \
	fi
	@until curl -s -m 2 localhost:13080/v2/version >/dev/null; do sleep 1; done
	@printf "$(C_BOLD)$(C_GREEN)✔ GNS3 is ready:$(C_RESET) http://localhost:13080/\n"

lab-down:
	docker rm -fv $(LAB)

p1: $(STAMP_DIR)/p1.stamp
	$(BADASS) up p1

p2: $(STAMP_DIR)/p2.stamp
	$(BADASS) up p2

p3: $(STAMP_DIR)/p3.stamp
	$(BADASS) up p3

$(STAMP_DIR)/p1.stamp: $(HOST_STAMP) $(ROUTER_STAMP) $(shell find P1 -type f 2>/dev/null) tests/badass.py
	@mkdir -p $(STAMP_DIR)
	$(BADASS) build p1
	@touch $@

$(STAMP_DIR)/p2.stamp: $(HOST_STAMP) $(ROUTER_STAMP) $(shell find P2 -type f 2>/dev/null) tests/badass.py
	@mkdir -p $(STAMP_DIR)
	$(BADASS) build p2
	@touch $@

$(STAMP_DIR)/p3.stamp: $(HOST_STAMP) $(ROUTER_STAMP) $(shell find P3 -type f 2>/dev/null) tests/badass.py
	@mkdir -p $(STAMP_DIR)
	$(BADASS) build p3
	@touch $@

p2-static:
	$(BADASS) mode static

p2-group:
	$(BADASS) mode group

p3-hosts:
	$(BADASS) hosts

stop:
	$(BADASS) down p1
	$(BADASS) down p2
	$(BADASS) down p3
	@rm -f $(STAMP_DIR)/p1.stamp $(STAMP_DIR)/p2.stamp $(STAMP_DIR)/p3.stamp

status:
	$(BADASS) status

test-p1 test-p2 test-p3:
	python3 tests/test_gns3.py $(subst test-,,$@)

test: p1 test-p1 p2 test-p2 p3 test-p3

clean:
	docker rm -fv $(LAB) 2>/dev/null || true
	$(BADASS) clean
	docker rmi -f alpine-router alpine-host $(LAB) 2>/dev/null || true
	rm -rf $(STAMP_DIR)

fclean: clean
	docker builder prune -af
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

prune: fclean
	docker ps -aq | xargs -r docker rm -fv
	docker system prune -af --volumes
	docker volume prune -af
