# AI Operator

## Overview

`ai_operator` contains a reinforcement learning control scaffold for power-system operation.

The project models operation as a sequential decision process:

1. solve the current power flow
2. observe the resulting electrical state
3. choose one control action
4. apply the action to the mutable grid model
5. solve a new power flow
6. score the new state
7. repeat

This is fundamentally different from a one-shot OPF or a static classifier. The agent is not asked to produce one final answer. It is asked to act, observe the consequence, and continue acting under feedback.

The folder currently includes:

- a single-agent sequential operator environment
- a multi-agent wrapper for aligned and adversarial agents
- typed action and observation objects
- reward computation and termination logic
- a first policy/value neural network
- single-agent actor-critic training
- multi-agent actor-critic training with one policy per logical group
- live plotting for training monitoring
- demos for rollout, training, multi-agent training, and scoped local-defender versus global-attacker scenarios

The code compiles, but it has not been fully runtime-validated in this sandbox against a real VeraGrid case.

## Why RL here

Power-system operation under intervention is naturally sequential.

An action such as opening a line or redispatching a generator changes the electrical state. That new state changes which next actions are safe, useful, or harmful. This dependence across time is exactly what a Markov decision process is meant to represent.

In this project:

- the state is derived from the solved power flow
- the action is an operator intervention
- the transition model is the grid physics plus the power-flow solve
- the reward measures whether the post-action state is better or worse

That makes RL the correct family of methods for the long-term objective, even if the first implementation is intentionally simple.

## Theory

### MDP interpretation

The base single-agent system is modeled as an MDP:

- state `s_t`
  the current grid condition after solving the PF at time step `t`
- action `a_t`
  one operator action applied at time step `t`
- transition `P(s_{t+1} | s_t, a_t)`
  induced by modifying the grid model and solving the next PF
- reward `r_t`
  a scalar evaluation of the post-action operating condition
- termination
  optional stop when the PF diverges or when a critical violation is reached

The multi-agent extension is a turn-based stochastic game built on top of the same physical simulator:

- one shared grid state
- one scheduled acting agent per turn
- per-agent reward alignment
- separate or shared policies depending on policy grouping

### Why turn-based multi-agent instead of simultaneous actions

The current design is turn-based because:

- it matches the current environment structure cleanly
- it keeps the physical state transition easy to inspect
- one action followed by one PF solve is simple and robust
- it is the minimal adversarial extension that can support defenders and attackers

Simultaneous action games can be added later, but they require additional design choices:

- how to merge concurrent commands
- how to resolve conflicts on the same asset
- whether the reward is based on intermediate or joint post-action states

### Positive and negative agents

The current multi-agent model uses aligned rewards.

Positive agents:

- try to maximize the base security reward

Negative agents:

- receive the sign-inverted reward
- therefore improve their own objective when the grid becomes less secure

Neutral agents:

- receive the base reward unchanged

This is a simple but useful first adversarial abstraction.

## Control problem

### Current supported action families

The first version supports two action families.

Branch switching:

- choose a branch index
- choose whether to open or close it

Generator redispatch:

- choose a generator index
- choose an active power delta in MW

This means the first agent can already express:

- topology changes
- active-power generation corrections

### Current unsupported action families

The code does not yet model:

- load shedding
- transformer tap changes
- shunt control
- explicit reactive power setpoint control
- multi-action bundles per step
- constrained action masks based on deeper operational logic

Each step still means exactly one action.

## Folder map

### Core environment and data model

[`actions.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/actions.py)

- `ActionCategory`
- `BranchSwitchAction`
- `GeneratorRedispatchAction`
- `OperatorAction`

[`config.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/config.py)

- `RewardWeights`
- `OperatorEnvConfig`

[`observations.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/observations.py)

- `ObservationData`
- `build_observation(...)`
- `flatten_observation(...)`

[`reward.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/reward.py)

- `RewardBreakdown`
- `compute_reward(...)`

[`environment.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/environment.py)

- `StepInfo`
- `VeraGridOperatorEnv`
- PF execution helpers
- action application helpers
- termination helpers

### Multi-agent layer

[`agents.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/agents.py)

- `AgentAlignment`
- `AgentActionScope`
- `AgentSpec`
- `MultiAgentConfig`
- `build_frank_and_jeffry_config(...)`
- `build_partitioned_defender_attacker_config(...)`

[`multi_agent_environment.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/multi_agent_environment.py)

- `MultiAgentReset`
- `MultiAgentStepInfo`
- `MultiAgentOperatorEnv`
- reward alignment helpers
- action scope projection helpers

### Learning and monitoring

[`network.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/network.py)

- `OperatorPolicyOutput`
- `PolicyActionSample`
- `OperatorPolicyNetwork`
- deterministic action decoding
- stochastic action sampling

[`trainer.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/trainer.py)

- rollout helpers
- random rollout
- policy rollout

[`training.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/training.py)

- `TrainingConfig`
- `EpisodeStep`
- `EpisodeSummary`
- `train_operator_policy(...)`

[`multi_agent_training.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/multi_agent_training.py)

- `MultiAgentTrainingConfig`
- `MultiAgentEpisodeStep`
- `PolicyGroupTrainer`
- `PolicyGroupSummary`
- `MultiAgentEpisodeSummary`
- `train_multi_agent_policy_system(...)`

[`live_plotting.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/live_plotting.py)

- `LivePlotConfig`
- `SingleAgentLivePlotter`
- `MultiAgentLivePlotter`

### Demos

[`demo.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/demo.py)

- rollout only

[`training_demo.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/training_demo.py)

- single-agent training demo
- live plotting enabled by default

[`multi_agent_training_demo.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/multi_agent_training_demo.py)

- multi-agent training demo
- live plotting enabled by default

[`scoped_multi_agent_demo.py`](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_operator/scoped_multi_agent_demo.py)

- N1 local defenders against N2 global attackers
- prints requested and applied actions after scope projection

## Environment mechanics

### Single-agent transition

At each step the base environment does this:

1. receive one `OperatorAction`
2. mutate the grid model
3. compile the grid into a numerical circuit
4. solve `multi_island_pf_nc(...)`
5. build the next observation
6. compute reward
7. compute termination and truncation

The power flow itself is therefore the transition engine.

### Observation contents

The current observation contains:

- current step index
- remaining steps
- bus voltage magnitudes
- bus voltage angles
- branch loadings
- branch active flags
- branch rates
- generator active powers
- generator minimum active powers
- generator maximum active powers

These are stored in `ObservationData`.

The network consumes the flattened version produced by `flatten_observation(...)`.

### Why these features

These variables were selected because they carry the minimum operational signal needed for the current control actions:

- voltage magnitude and angle describe bus state
- branch loading and active flags describe topology stress and current switching status
- generator `P`, `Pmin`, and `Pmax` describe redispatch state and headroom

This is not the only valid feature set, but it is a coherent baseline.

## Reward theory

### Current reward structure

The reward is computed on the post-action state.

Current terms:

- voltage violation penalty
- branch overload penalty
- generator limit penalty
- switching action penalty
- redispatch magnitude penalty
- secure-operation bonus
- PF divergence penalty

### Why post-action reward

The policy should learn the consequence of what it did, not just the quality of the state it entered. Computing reward after the new PF solve makes the training target causally correct.

### Interpretation of each term

Voltage violation penalty:

- discourages operating outside bus voltage limits
- pushes the policy toward voltage feasibility

Branch overload penalty:

- discourages thermal or contingency overloads
- pushes the policy away from stressed topology states

Generator limit penalty:

- discourages unrealistic redispatch beyond bounds
- makes redispatch physically meaningful

Action penalty:

- discourages unnecessary interventions
- prevents the trivial solution of constantly switching or oscillating generation

Secure-operation bonus:

- rewards fully compliant operating states
- provides a sparse positive signal when the system is healthy

PF divergence penalty:

- strongly penalizes moves that lead to non-convergent states
- teaches the policy to stay inside the solvable part of the state space

### Reward is not final

The current reward is an engineering baseline. It will almost certainly evolve after real runs reveal:

- unwanted oscillatory behavior
- too much switching
- too little aggressiveness under severe violations
- bad attacker incentives
- exploitability of specific reward terms

## Metrics

### Single-agent training metrics

The single-agent trainer currently records:

- episode reward
- actor loss
- value loss
- entropy
- episode step count

Episode reward:

- sum of rewards over the episode
- primary high-level indicator of whether the learned behavior is improving

Actor loss:

- policy-gradient loss term
- not directly an operational metric
- useful mainly to verify training is numerically active

Value loss:

- critic fit error
- useful to detect when the critic is underfitting returns

Entropy:

- rough exploration indicator
- high entropy means stochastic behavior
- low entropy means policy collapse or confident action selection

### Multi-agent training metrics

The multi-agent trainer records one summary per policy group:

- total aligned reward
- actor loss
- value loss
- entropy
- step count for that group

This matters because defender and attacker progress must be read separately.

In adversarial training, raw total episode reward alone is not enough. You need to know:

- whether defenders are improving
- whether attackers are improving
- whether one side is collapsing
- whether one side is starved of turns

### Environment-side metrics worth adding later

The current code does not yet log these as first-class metrics, but they are natural next additions:

- PF convergence rate
- number of voltage violations
- number of overloaded branches
- number of scope-projected actions
- average redispatch magnitude
- switching frequency
- defender-versus-attacker net advantage

## Neural network

### Current architecture

The first policy is a dense multilayer perceptron with a shared trunk and split heads.

Shared trunk:

- linear
- ReLU
- linear
- ReLU

Heads:

- action-category head
- branch-index head
- branch open/close head
- generator-index head
- generator delta head
- value head

### Why split heads instead of one flat action vector

The action is structured:

- choose a family
- choose an asset
- choose a parameter

A split-head network respects that structure and scales better when more controllable assets are added.

### Current limitation of the architecture

The current policy is dense and flat. Power systems are graphs, so a graph policy may become preferable later, especially when:

- grid size varies a lot
- locality matters more strongly
- region-aware control becomes more important

## Single-agent training

### Current algorithm

The single-agent trainer uses a minimal actor-critic update.

For each episode:

1. reset environment
2. sample stochastic actions from the policy
3. collect rewards, log probabilities, values, and entropies
4. compute discounted returns
5. compute advantages as return minus detached value
6. compute actor loss
7. compute value loss
8. compute entropy bonus
9. optimize with Adam

### What it is not

The current trainer is not:

- PPO
- GAE
- A2C with batched environments
- replay-based off-policy RL
- distributed training

It is intentionally the smallest thing that makes the project actually train.

## Multi-agent training

### Current adversarial model

The multi-agent trainer uses one policy per logical `policy_group`.

For Frank and Jeffry:

- `defender` policy group
- `attacker` policy group

For each episode:

1. reset the shared electrical world
2. schedule one acting agent
3. select that agent's policy by `policy_group`
4. sample one action
5. apply the action
6. compute aligned reward for the acting agent
7. continue until stop
8. split the full trajectory by policy group
9. update each policy group from its own turns

### Why policy groups

This is the right first abstraction because later you may want:

- one shared policy for several defenders
- one shared policy for several attackers
- one policy per agent

The `policy_group` field supports all of those with less redesign.

### What is still missing in adversarial learning

The current multi-agent trainer does not yet implement:

- self-play leagues
- centralized critics
- opponent-aware critics
- opponent modeling
- simultaneous actions
- population-based training
- batched parallel worlds

So this is an adversarial baseline, not yet a mature game-learning system.

## Scoped defenders versus global attackers

### Current territorial demo

The scoped demo builds:

- `N1` positive defenders
- `N2` negative attackers

The defenders receive disjoint contiguous partitions of:

- branch indices
- generator indices

Attackers remain unrestricted.

### Important theoretical limitation

This current territorial split is index-based, not topology-aware.

That means it is not yet a true electrical-area decomposition. It is still useful, because it lets the code express:

- local agents
- global adversaries
- action projection into allowed regions

But it should eventually be replaced by a topology-aware partitioning based on buses, areas, or graph clustering.

### Requested action versus applied action

In the scoped multi-agent setup, an agent may request an action outside its territory.

The wrapper then projects that action into the allowed scope.

This is why the scoped demo prints both:

- requested action
- applied action

That projection rate is itself an important future metric because too many projected actions would mean:

- the policy does not understand its territory
- the action encoding is mismatched to the scope restriction

## Live plotting

### What exists

The project now includes optional live plotting through `LivePlotConfig`.

Single-agent live plotting shows:

- episode reward
- actor loss
- value loss
- entropy

Multi-agent live plotting shows:

- per-policy-group reward
- per-policy-group actor loss

### Why these plots matter

Reward curves tell you if the policy is improving operationally.

Loss curves tell you if optimization is active and numerically stable.

Entropy tells you whether the policy is still exploring or has collapsed into a narrow behavior pattern.

In multi-agent runs, per-group curves matter because:

- one side may improve while the other collapses
- one side may dominate because of reward scaling
- one side may stop receiving useful gradient signal

### Current plotting behavior

If `matplotlib` is available:

- a live window updates during training

If `matplotlib` is not available:

- plotting silently becomes a no-op
- training still runs

## Checkpointing

Single-agent checkpoints are stored under:

`trunk/ai/ai_operator/checkpoints`

Multi-agent checkpoints are stored under:

`trunk/ai/ai_operator/checkpoints_multi_agent`

Stored contents currently include:

- episode index
- model state
- optimizer state
- selected hyperparameters

This is enough to resume or inspect the learned policies later.

## Public entry points

Rollout demo:

```python
from trunk.ai.ai_operator.demo import run_demo
```

Single-agent training demo:

```python
from trunk.ai.ai_operator.training_demo import run_training_demo
```

Multi-agent training demo:

```python
from trunk.ai.ai_operator.multi_agent_training_demo import run_multi_agent_training_demo
```

Scoped N1-versus-N2 demo:

```python
from trunk.ai.ai_operator.scoped_multi_agent_demo import run_scoped_multi_agent_demo
```

Single-agent training API:

```python
from trunk.ai.ai_operator.training import train_operator_policy
```

Multi-agent training API:

```python
from trunk.ai.ai_operator.multi_agent_training import train_multi_agent_policy_system
```

Live plotting config:

```python
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
```

## Usage examples

### Single-agent rollout

```python
from trunk.ai.ai_operator.demo import run_demo

history = run_demo(
    grid_path="files/IEEE 9 Bus.veragrid",
    steps=10,
    seed=7,
)
```

### Single-agent training with live plotting

```python
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.training import TrainingConfig
from trunk.ai.ai_operator.training import train_operator_policy

policy_network, history = train_operator_policy(
    grid_path="files/IEEE 9 Bus.veragrid",
    training_config=TrainingConfig(
        episodes=100,
        max_steps_per_episode=32,
        learning_rate=1.0e-4,
        gamma=0.99,
    ),
    live_plot_config=LivePlotConfig(
        enabled=True,
        refresh_interval=1,
        window_title="Single Agent Training Monitor",
    ),
)
```

### Frank versus Jeffry training with live plotting

```python
from trunk.ai.ai_operator.agents import build_frank_and_jeffry_config
from trunk.ai.ai_operator.live_plotting import LivePlotConfig
from trunk.ai.ai_operator.multi_agent_training import MultiAgentTrainingConfig
from trunk.ai.ai_operator.multi_agent_training import train_multi_agent_policy_system

group_trainers, history = train_multi_agent_policy_system(
    grid_path="files/IEEE 9 Bus.veragrid",
    multi_agent_config=build_frank_and_jeffry_config(),
    training_config=MultiAgentTrainingConfig(
        episodes=100,
        max_turns_per_episode=64,
        learning_rate=1.0e-4,
        gamma=0.99,
    ),
    live_plot_config=LivePlotConfig(
        enabled=True,
        refresh_interval=1,
        window_title="Frank vs Jeffry Training",
    ),
)
```

### N1 local defenders against N2 global attackers

```python
from trunk.ai.ai_operator.scoped_multi_agent_demo import run_scoped_multi_agent_demo

history = run_scoped_multi_agent_demo(
    grid_path="files/IEEE 9 Bus.veragrid",
    n_defenders=3,
    n_attackers=2,
    turns=20,
    seed=7,
)
```

## Current assumptions

The code currently assumes:

- VeraGrid PF outputs are NumPy arrays
- branch and generator collections are available from the grid API
- branches expose `active` or `enabled`
- generators expose `P`, and maybe `Pmin` and `Pmax`
- one action per step is sufficient for the baseline design

These assumptions are reasonable for a first slice, but they are not yet fully validated across a broad grid library.

## Current weaknesses

### Runtime validation gap

The code has not been fully exercised end to end in this sandbox against a real case because of environment restrictions around the VeraGrid runtime path.

### Minimal RL algorithms

Both single-agent and multi-agent trainers are intentionally minimal.

They are useful for getting behavior, gradients, and reward curves, but they are not yet strong RL baselines.

### Defensive environment internals

Some parts of the environment still use defensive checks because the exact runtime device class behavior has not been confirmed across all cases.

### Dense observation encoding

The policy currently sees a dense flattened vector rather than a graph-structured encoding.

### No action masking

The policies can still choose actions that are syntactically valid but operationally weak.

### Territorial decomposition is not yet topological

Scoped defenders use index partitions, not true electrical regions.

## Recommended next work

1. Run one real single-agent training session on a concrete grid and inspect the first runtime failure.
2. Run one real multi-agent training session and inspect defender versus attacker curve behavior.
3. Add explicit metrics for PF convergence rate, violation count, and projected-scope action rate.
4. Replace index-based defender territories with topology-aware regions.
5. Add action masking.
6. Upgrade the trainer toward PPO or another stronger on-policy method.
7. Consider a graph policy once runtime stability is confirmed.
8. Add tests for environment stepping, reward terms, checkpointing, and policy output shapes.

## Relation to the rest of `trunk/ai`

This folder is distinct from `grid_ai` and `clean_room`.

Those areas focus on learning electrical structure or approximating power-flow behavior.

This folder focuses on control under interaction:

- state
- action
- transition
- reward
- repeated intervention

So this folder is the operator-control branch of the AI work.

## Current status

Current maturity:

- single-agent environment: present
- multi-agent environment: present
- policy network: present
- single-agent training: present
- multi-agent training: present
- live plotting: present
- scoped defender-versus-attacker demo: present
- detailed documentation: present
- runtime validation: still missing
- tests: still missing
- advanced RL algorithms: still missing

The project is now structurally ready for real experiments.
