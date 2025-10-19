import { get_logger, is_client_context } from "shared/tver/utility/utils"

export abstract class Handler {
    public Type = is_client_context()? "Client" : "Server"
    public Activated = false
    public log = get_logger(this.Type.upper())

    private readonly _registered: ModuleScript[] = []

    constructor () {}

    public Register(ToLoad: Folder | ModuleScript) {
        if (this.Activated) {this.log.w("Cant Register after " + this.Type + " Was Activated"); return}

        if (ToLoad.IsA("ModuleScript")) {
            this._registered.push(ToLoad)
        } else if (ToLoad.IsA("Folder")) {
            ToLoad.GetDescendants().forEach((instance) => {
                if (instance.IsA("ModuleScript")) {
                    this._registered.push(instance)
                }
            })
        } else {
            this.log.w("Cant Register " + ToLoad)
        }
    }

    public Load() {
        if (this.Activated) {this.log.w(this.Type + " cant be loaded after activation!"); return}

        const _failed: defined[] = []

        this._registered.forEach((module) => {
            let success, err = pcall(() => {
                require(module)
            })
            if (err) {
                _failed.push(err)
            }
        })

        _failed.forEach((err) => {
            this.log.w(err)
        })
    }
}