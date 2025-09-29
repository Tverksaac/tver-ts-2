import { StateMachine } from "shared/tver/classes/fundamental/state_machine";

const states = new StateMachine<["Ready", "On", "Off", "Ended"]>()