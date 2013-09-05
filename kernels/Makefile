# user can specify the node and variant but we used M1_Released 
VARIANT ?= released
NODE ?= M1

NODES=M1 Rim Rim64

help:
	@echo
	@echo "BUILDs 		-- A one shut activity that untars and patches the kernel for a Node type and variant."
	@echo
	@echo " 	Build a kernel for the specified node"
	@echo " 	Current nodes are : $(NODES)"
	@echo " 	example: builds the 'released' version of M1 kernel"
	@echo " 		make M1"
	@echo " 	example: builds Joe's variant of M1 kernel"
	@echo " 		VARIANT=joe make M1"
	@echo
	@echo "VARIANTs 	-- Custom kernel version for a specific node."
	@echo
	@echo "     To create your own kernel variant, create a patch set and config for that variant"
	@echo "     Example : cp patch_0000.M1.released.base patch_0010.M1.kdump.base"
	@echo "          or : ln -s patch_0000.M1.released.base patch_0010.M1.kdump.base"
	@echo "     to build it, execute: VARIANT=joe make M1"
	@echo
	@echo "SAVING     	-- to save your work, you need to regenerate the patch."
	@echo
	@echo "     You'll have to do this by hand using the original tarball against your distclean'ed new source."
	@echo "     Then execute: NODE=M1 make patch"
	@echo "     Or          : NODE=M1 VARIANT=kdump make patch"
	@echo "     This will genarte a patch in file M1_released/patch, which you can add as the next sequenced patch"
	@echo "     in patches/patchXXXX_M1_released.patchname. All patches are applied in order of their XXXX value."
	@echo "     Note that if that patch applies to multiple variants, create symb links for it. And test the"
	@echo "     patches for that variant."
	@echo
	@echo "CLEANUP  	-- run 'make cleanall'"

Rim_kver = 3.1.aufs
Rim64_kver = 3.1.aufs
M1_kver = 3.1.1

$(NODES):
	@mkdir -p $@_$(VARIANT)
	@[ "patches/patch.$@.$(VARIANT)" ] || ( echo "Patch files patches/\*.$@.$(VARIANT), not found." && exit 1 )
	@[ -f configs/config.$@.$(VARIANT) ] || ( echo "Config file configs/config.$@.$(VARIANT), not found." && exit 1 )
	@[ -d $@/linux-$($(@)_source) ] || \
		( \
			echo -n "Un-tarring kernel source..." ;\
			mkdir -p $@_$(VARIANT) ;\
			( \
				cd $@_$(VARIANT) && tar xjf ../source/linux-$($@_kver).tar.bz2  ;\
			) ;\
			echo "Done." ;\
		)
	@./patchkern $($(@)_kver) $@ $(VARIANT)
	@cp configs/config.$@.$(VARIANT) $@_$(VARIANT)/linux-$($(@)_kver)/.config
	@ echo "To build, goto the $@_$(VARIANT)/linux-$($(@)_kver) directory and execute a make."

patch:
	@./makepatch "$($(NODE)_kver)" "$(NODE)" "$(VARIANT)"
        

cleanall:
	@for node in $(NODES); do /bin/rm -rf $$node*; done
