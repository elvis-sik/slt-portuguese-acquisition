Read `AGENTS.md` and verify that the scientific pilot passed and explicit human approval is recorded in the decision log. Freeze configs and data hashes. Run final behavioral trajectories in priority order: Portuguese seed A, shuffled Portuguese, matched English, Portuguese seed B. Use bounded jobs and checkpoint by target tokens. Evaluate every checkpoint and update the cost projection after each trajectory.

Do not inspect or optimize final LLC until behavior outputs and checkpoint selection rules are frozen. Stop if the projected total exceeds the hard budget or runtime gate.
